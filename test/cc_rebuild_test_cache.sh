#!/bin/bash

# Only intended for use on MacOS and/or Linux local install
TESTS=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ROOT="$(dirname "$TESTS")"
echo "$ROOT"
cd "$ROOT" || exit 1


# echo "Testing inspection: should take about 2-4 minutes..."
# "$PYTEST" test/test_inspection.py -m 'regen' -x || echo "Failed to regenerate inspections" && exit 1
# "$PYTEST" test/test_inspection.py -m 'not regen' -x || echo "Failed to load cached inspections" && exit 1


# echo "Testing data preparation: should take less than 5 minutes..."
# "$PYTEST" test/test_prepare.py -m 'regen' -x || echo "Failed to generate prepared data" && exit 1
# "$PYTEST" test/test_prepare.py -m 'not regen' -x || echo "Failed to load cached prepared data" && exit 1

# echo "Testing association computations: should take less than 5 minutes..."
# "$PYTEST" test/test_associate.py -m 'regen' -x || echo "Failed to gen associations" && exit 1
# "$PYTEST" test/test_associate.py -m 'not regen' -x || echo "Failed to load cached associations" && exit 1

# echo "Testing predictions: should take about 8-10 minutes..."
# "$PYTEST" test/test_predict.py::test_predict_fast -x || echo "Failed to make predictions" && exit 1
# "$PYTEST" test/test_predict.py::test_predict_cached_fast -x || echo "Failed to load cached predictions" && exit 1

# echo "Testing fast feature selection method: will take hours, but this"
# echo "is the last test, so if the first many pass, *probably* things are okay..."
# "$PYTEST" test/test_selection.py -m 'fast' -x || echo "Failed to do selection" && exit 1



echo "Testing inspection: should take about 2-4 minutes..."
"$PYTEST" test/test_inspection.py -m 'regen' -x
"$PYTEST" test/test_inspection.py -m 'not regen' -x


echo "Testing data preparation: should take less than 5 minutes..."
"$PYTEST" test/test_prepare.py -m 'regen' -x
"$PYTEST" test/test_prepare.py -m 'not regen' -x

echo "Testing association computations: should take less than 5 minutes..."
"$PYTEST" test/test_associate.py -m 'regen' -x
"$PYTEST" test/test_associate.py -m 'not regen' -x

echo "Testing predictions: should take about 8-10 minutes..."
"$PYTEST" test/test_predict.py::test_predict_fast -x
"$PYTEST" test/test_predict.py::test_predict_cached_fast -x

echo "Testing fast feature selection method: will take hours, but this"
echo "is the last test, so if the first many pass, *probably* things are okay..."
"$PYTEST" test/test_selection.py -m 'fast' -x