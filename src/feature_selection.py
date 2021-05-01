# TODO
# - implement step-up feature selection
# - implement step-down feature selection
# - extract N largest PCA components as features
# - choose features with largest univariate separation in classes (d, AUC)
# - smarter methods
#   - remove correlated features
#   - remove constant features (no variance)

# NOTE: feature selection is PRIOR to hypertuning, but "what features are best" is of course
# contengent on the choice of regressor / classifier
# correct way to frame this is as an overall derivative-free optimization problem where the
# classifier choice is *just another hyperparameter*
import sys

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from typing import cast, no_type_check
from typing_extensions import Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from numpy import ndarray
from pandas import DataFrame, Series

from featuretools.selection import (
    remove_single_value_features,
    remove_highly_correlated_features,
    remove_low_information_features,
)
from sklearn.decomposition import PCA, KernelPCA
from sklearn.feature_selection import (
    VarianceThreshold,
    SelectPercentile,
    GenericUnivariateSelect,
    RFECV,
    SelectFromModel,
)
from sklearn.metrics import roc_auc_score
from sklearn.svm import LinearSVC
from sklearn.linear_model import LassoCV, LinearRegression

from src.constants import DATADIR, SEED, UNCORRELATED
from src._sequential import SequentialFeatureSelector

# see https://scikit-learn.org/stable/modules/feature_selection.html
# for SVM-based feature selection, LASSO based feature selction, and RF-based feature-selection
# using SelectFromModel
FlatArray = Union[DataFrame, Series, ndarray]


def cohens_d(df: DataFrame) -> Series:
    """For each feature in `df`, compute the absolute Cohen's d values

    Parameters
    ----------
    df: DataFrame
        DataFrame with shape (n_samples, n_features + 1) and target variable in column "target"
    """
    X = df.drop(columns="target")
    y = df["target"].copy()
    x1, x2 = X.loc[y == 0, :], X.loc[y == 1, :]
    n1, n2 = len(x1) - 1, len(x2) - 1
    sd1, sd2 = np.std(x1, ddof=1, axis=0), np.std(x2, ddof=1, axis=0)
    sd_pools = np.sqrt((n1 * sd1 + n2 * sd2) / (n1 + n2))
    m1, m2 = np.mean(x1, axis=0), np.mean(x2, axis=0)
    ds = np.abs(m1 - m2) / sd_pools
    return ds


def auroc(df: DataFrame) -> Series:
    """For each feature in `df` compute rho, the common-language effect size (see Notes) via the
    area-under-the-ROC curve (AUC), and rescale this effect size to allow sorting across features.

    Parameters
    ----------
    df: DataFrame
        DataFrame with shape (n_samples, n_features + 1) and target variable in column "target"

    Notes
    -----
    This is equivalent to calculating U / abs(y1*y2), where `y1` and `y2` are the subgroup sizes,
    and U is the Mann-Whitney U, and is also sometimes referred to as Herrnstein's rho [1] or "f",
    the "common-language effect size" [2].

    Note we also *must* rescale as rho is implicity "signed", with values above 0.5 indicating
    separation in one direction, and values below 0.5 indicating separation in the other.

    [1] Herrnstein, R. J., Loveland, D. H., & Cable, C. (1976). Natural concepts in pigeons.
        Journal of Experimental Psychology: Animal Behavior Processes, 2, 285-302

    [2] McGraw, K.O.; Wong, J.J. (1992). "A common language effect size statistic". Psychological
        Bulletin. 111 (2): 361–365. doi:10.1037/0033-2909.111.2.361.
    """
    X = df.drop(columns="target")
    y = df["target"].copy()

    aucs = Series(data=[roc_auc_score(y, X[col]) for col in X], index=X.columns)
    rescaled = (aucs - 0.5).abs()
    return rescaled


def correlations(df: DataFrame, method: Literal["pearson", "spearman"] = "pearson") -> Series:
    """For each feature in `df` compute the ABSOLUTE correlation with the target variable.

    Parameters
    ----------
    df: DataFrame
        DataFrame with shape (n_samples, n_features + 1) and target variable in column "target"

    """
    X = df.drop(columns="target")
    y = df["target"].copy()
    return X.corrwith(y, method=method).abs()


def remove_correlated_custom(df: DataFrame, threshold: float = 0.95) -> DataFrame:
    """TODO: implement this to greedily combine highly-correlated features instead of just dropping"""
    # corrs = np.corrcoef(df, rowvar=False)
    # rows, cols = np.where(corrs > threshold)
    # correlated_feature_pairs = [(df.columns[i], df.columns[j]) for i, j in zip(rows, cols) if i < j]
    # for pair in correlated_feature_pairs[:10]:
    #     print(pair)
    # print(f"{len(correlated_feature_pairs)} correlated feature pairs total")
    raise NotImplementedError()


def remove_weak_features(df: DataFrame, decorrelate: bool = True) -> DataFrame:
    """Remove constant, low-information, and highly-correlated (> 0.95) features"""
    if UNCORRELATED.exists():
        return pd.read_json(UNCORRELATED)
    print("Starting shape: ", df.shape)
    df_v = remove_single_value_features(df)
    print("Shape after removing constant features: ", df_v.shape)
    df_i = remove_low_information_features(df_v)
    print("Shape after removing low-information features: ", df_i.shape)
    if not decorrelate:
        return df_i
    print(
        "Removing highly-correlated features."
        "NOTE: this could take a while when there are 1000+ features."
    )
    df_c = remove_highly_correlated_features(df_i)
    print("Shape after removing highly-correlated features: ", df_c.shape)
    df_c.to_json(UNCORRELATED)
    print(f"Saved uncorrelated features to {UNCORRELATED}")


def select_features_by_univariate_rank(
    df: DataFrame, metric: Literal["d", "auc", "pearson", "spearman"], n_features: int = 10
) -> DataFrame:
    """Naively select features based on their univariate relation with the target variable.

    Parameters
    ----------
    df: DataFrame
        Data with target in column named "target".

    metric: "d" | "auc" | "pearson" | "spearman"
        Metric to compute for each feature

    n_features: int = 10
        How many features to select

    Returns
    -------
    reduced: DataFrame
        Data with reduced feature set.
    """
    importances = None
    if metric.lower() == "d":
        importances = cohens_d(df).sort_values(ascending=False)
    elif metric.lower() == "auc":
        importances = auroc(df).sort_values(ascending=False)
    elif metric.lower() in ["pearson", "spearman"]:
        importances = correlations(df, method=metric).sort_values(ascending=False)
    else:
        raise ValueError("Invalid metric")
    strongest = importances[:n_features]
    return df.loc[:, strongest.index]


def get_pca_features(df: DataFrame, n_features: int = 10) -> DataFrame:
    """Return a DataFrame that is the original DataFrame projected onto the space described by first
    `n_features` principal components

    Parameters
    ----------
    df: DataFrame
        DataFrame to process

    n_features: int = 10
        Number of final features (components) to use.

    Returns
    -------
    reduced: DataFrame
        Feature-reduced DataFrame
    """
    pca = PCA(n_features, svd_solver="full", whiten=True)
    reduced = pca.fit_transform(df)
    return DataFrame(data=reduced, columns=[f"pca-{i}" for i in range(reduced.shape[1])])


def get_kernel_pca_features(df: DataFrame, n_features: int = 10) -> DataFrame:
    """Return a DataFrame that is reduced via KernelPCA to `n_features` principal components.

    Parameters
    ----------
    df: DataFrame
        DataFrame to process

    n_features: int = 10
        Number of final features (components) to use.

    Returns
    -------
    reduced: DataFrame
        Feature-reduced DataFrame
    """
    kpca = KernelPCA(n_features, kernel="rbf", random_state=SEED, n_jobs=-1)
    reduced = kpca.fit_transform(df)
    return DataFrame(data=reduced, columns=[f"kpca-{i}" for i in range(reduced.shape[1])])


def select_stepwise_features(
    df: DataFrame,
    estimator: Any = None,
    n_features: int = 10,
    direction: Literal["forward", "backward"] = "forward",
) -> DataFrame:
    selector = SequentialFeatureSelector(
        estimator,
        n_features_to_select=n_features,
        direction=direction,
        scoring="accuracy",
        cv=3,
        n_jobs=-1,
    )
    X = df.drop(columns="target")
    y = (
        df["target"].copy().astype(int)
    )  # ensure cross-val uses stratified by making it int (see docs)
    selector.fit(X, y)
    column_idx = selector.get_support()
    reduced = X.loc[:, column_idx].copy()
    reduced["target"] = y.copy()
    return reduced