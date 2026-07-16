import pandas as pd


def _validate_inputs(left: pd.Series, right: pd.Series) -> None:
    if not left.index.equals(right.index):
        raise ValueError("left and right series must have the same index")


def cross_above(left: pd.Series, right: pd.Series) -> pd.Series:
    _validate_inputs(left, right)
    return (left > right) & (left.shift(1) <= right.shift(1))


def cross_below(left: pd.Series, right: pd.Series) -> pd.Series:
    _validate_inputs(left, right)
    return (left < right) & (left.shift(1) >= right.shift(1))
