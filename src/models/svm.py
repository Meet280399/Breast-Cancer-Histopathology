from __future__ import annotations

# fmt: off
import sys  # isort: skip
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Type

from optuna import Trial

from pandas import DataFrame, Series  # isort: skip
ROOT = Path(__file__).resolve().parent.parent.parent  # isort: skip
sys.path.append(str(ROOT))  # isort: skip
# fmt: on

import time
from copy import deepcopy
from warnings import catch_warnings, filterwarnings

import numpy as np
import optuna
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.model_selection import cross_validate as cv
from sklearn.svm import SVC, SVR, LinearSVC, LinearSVR

from src._constants import SEED
from src.models.base import NEG_MAE, DfAnalyzeModel


class SVMEstimator(DfAnalyzeModel):
    def __init__(self, model_args: Optional[Mapping] = None) -> None:
        super().__init__(model_args)
        self.is_classifier = True
        self.fixed_args = dict(cache_size=1000)
        self.default_args = dict(kernel="rbf")

    def model_cls_args(self, full_args: dict[str, Any]) -> tuple[type, dict[str, Any]]:
        is_rbf = full_args["kernel"]
        # plain SVC is excruciatingly slow even on small datasets for many
        # C and gamma values. So we switch to Linear here despite the fact
        # that, in theory, it confounds Optuna by ignoring a lot of gamma
        # values.
        # TODO: Switch to SGDClassifer and Kernel Approximation here
        # for large N
        if self.is_classifier:
            model_cls = SVC if is_rbf else LinearSVC
        else:
            model_cls = SVR if is_rbf else LinearSVR

        args = deepcopy(full_args)
        if not is_rbf:
            args.pop("cache_size")
            args.pop("gamma")
            args.pop("kernel")

        return model_cls, args

    def optuna_args(self, trial: Trial) -> dict[str, str | float | int]:
        return dict(
            kernel=trial.suggest_categorical("kernel", choices=["rbf", "linear"]),
            # combination of large C and small gamma can multiply training time
            # by orders of magnitude...
            C=trial.suggest_float("C", 1e-10, 1e3, log=True),
            gamma=trial.suggest_float("gamma", 1e-7, 1e5, log=True),
        )


class SVMClassifier(SVMEstimator):
    def __init__(self, model_args: Optional[Mapping] = None) -> None:
        super().__init__(model_args)
        self.is_classifier = True
        self.needs_calibration = True
        self.model_cls = SVC

    def fit(self, X_train: DataFrame, y_train: Series) -> None:
        if self.model is None:
            kwargs = {**self.fixed_args, **self.model_args}
            self.model = self.model_cls(**kwargs)
        self.model.fit(X_train, y_train)


class SVMRegressor(SVMEstimator):
    def __init__(self, model_args: Optional[Mapping] = None) -> None:
        super().__init__(model_args)
        self.is_classifier = False
        self.model_cls = SVR
