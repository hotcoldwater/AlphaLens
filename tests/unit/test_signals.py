import pandas as pd

from services.api.app.backtest_engine.signals import cross_above, cross_below


def test_cross_above_is_emitted_only_on_transition():
    left = pd.Series([1, 2, 3, 2, 4])
    right = pd.Series([2, 2, 2, 2, 2])
    assert cross_above(left, right).tolist() == [False, False, True, False, True]


def test_cross_below_is_emitted_only_on_transition():
    left = pd.Series([3, 2, 1, 2, 0])
    right = pd.Series([2, 2, 2, 2, 2])
    assert cross_below(left, right).tolist() == [False, False, True, False, True]


def test_cross_requires_matching_indexes():
    left = pd.Series([1], index=["a"])
    right = pd.Series([2], index=["b"])
    try:
        cross_above(left, right)
    except ValueError as error:
        assert "same index" in str(error)
    else:
        raise AssertionError("expected mismatched indexes to be rejected")
