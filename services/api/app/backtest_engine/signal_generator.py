import operator as operator_module

import pandas as pd

from ..enums import IndicatorType, LogicType, OperatorType
from ..schemas.strategy_schema import (
    Condition,
    IndicatorReference,
    RuleSet,
    Strategy,
    ValueReference,
)
from .indicators import ema, rsi, sma
from .signals import cross_above, cross_below


def generate_strategy_signals(
    data: pd.DataFrame, strategy: Strategy, signal_data: dict[str, pd.DataFrame] | None = None
) -> tuple[pd.Series, pd.Series]:
    """Compile the supported Strategy rules into entry and exit Boolean series.

    `signal_data` supplies OHLCV for any symbol an IndicatorReference references
    via its optional `symbol` field, other than the strategy's own traded data.
    """
    return (
        evaluate_rules(data, strategy.entry_rules, signal_data),
        evaluate_rules(data, strategy.exit_rules, signal_data),
    )


def evaluate_rules(
    data: pd.DataFrame, rules: RuleSet, signal_data: dict[str, pd.DataFrame] | None = None
) -> pd.Series:
    if data.empty:
        raise ValueError("data must not be empty")
    results = [evaluate_condition(data, condition, signal_data) for condition in rules.conditions]
    combined = results[0]
    for result in results[1:]:
        combined = combined & result if rules.logic == LogicType.AND else combined | result
    return combined.fillna(False).astype(bool)


def evaluate_condition(
    data: pd.DataFrame, condition: Condition, signal_data: dict[str, pd.DataFrame] | None = None
) -> pd.Series:
    left = _resolve_operand(data, condition.left, signal_data)
    right = _resolve_operand(data, condition.right, signal_data)
    comparisons = {
        OperatorType.GREATER_THAN: operator_module.gt,
        OperatorType.GREATER_THAN_OR_EQUAL: operator_module.ge,
        OperatorType.LESS_THAN: operator_module.lt,
        OperatorType.LESS_THAN_OR_EQUAL: operator_module.le,
        OperatorType.EQUAL: operator_module.eq,
    }
    if condition.operator in comparisons:
        result = comparisons[condition.operator](left, right)
    elif condition.operator == OperatorType.CROSS_ABOVE:
        result = cross_above(left, right)
    elif condition.operator == OperatorType.CROSS_BELOW:
        result = cross_below(left, right)
    else:  # The enum makes this unreachable unless a new operator is added.
        raise ValueError(f"unsupported operator: {condition.operator}")
    return result.fillna(False).astype(bool)


def _resolve_operand(
    data: pd.DataFrame,
    operand: IndicatorReference | ValueReference,
    signal_data: dict[str, pd.DataFrame] | None = None,
) -> pd.Series:
    if isinstance(operand, ValueReference):
        return pd.Series(float(operand.value), index=data.index)
    frame = data
    if signal_data is not None and operand.symbol is not None:
        if operand.symbol not in signal_data:
            raise ValueError(f"missing signal data for {operand.symbol}")
        frame = signal_data[operand.symbol]
    return _indicator_series(frame, operand)


def _indicator_series(data: pd.DataFrame, reference: IndicatorReference) -> pd.Series:
    indicator = reference.indicator
    column_map = {
        IndicatorType.OPEN: "open",
        IndicatorType.HIGH: "high",
        IndicatorType.LOW: "low",
        IndicatorType.CLOSE: "close",
        IndicatorType.VOLUME: "volume",
    }
    if indicator in column_map:
        column = column_map[indicator]
        if column not in data:
            raise ValueError(f"data must contain {column} column")
        return data[column].astype(float)
    if indicator == IndicatorType.SMA:
        return sma(data["close"].astype(float), reference.period)
    if indicator == IndicatorType.EMA:
        return ema(data["close"].astype(float), reference.period)
    if indicator == IndicatorType.RSI:
        return rsi(data["close"].astype(float), reference.period)
    if indicator == IndicatorType.RETURN:
        return data["close"].astype(float).pct_change()
    if indicator == IndicatorType.N_DAY_RETURN:
        return data["close"].astype(float).pct_change(reference.period)
    if indicator == IndicatorType.N_DAY_HIGH:
        return data["high"].astype(float).rolling(reference.period, min_periods=reference.period).max()
    if indicator == IndicatorType.N_DAY_LOW:
        return data["low"].astype(float).rolling(reference.period, min_periods=reference.period).min()
    if indicator == IndicatorType.VOLUME_SMA:
        return sma(data["volume"].astype(float), reference.period)
    if indicator == IndicatorType.DAY_OF_WEEK:
        # Monday=0 .. Friday=4, to match Python's / pandas' own convention.
        return pd.Series(data.index.dayofweek, index=data.index, dtype=float)
    if indicator == IndicatorType.MONTH_OF_YEAR:
        return pd.Series(data.index.month, index=data.index, dtype=float)
    if indicator == IndicatorType.CONSECUTIVE_UP_DAYS:
        return _consecutive_streak(data["close"].astype(float), rising=True)
    if indicator == IndicatorType.CONSECUTIVE_DOWN_DAYS:
        return _consecutive_streak(data["close"].astype(float), rising=False)
    if indicator == IndicatorType.GAP_RETURN:
        previous_close = data["close"].astype(float).shift(1)
        return data["open"].astype(float) / previous_close - 1
    if indicator == IndicatorType.N_WEEK_HIGH:
        window = reference.period * _TRADING_DAYS_PER_WEEK
        return data["high"].astype(float).rolling(window, min_periods=window).max()
    if indicator == IndicatorType.N_WEEK_LOW:
        window = reference.period * _TRADING_DAYS_PER_WEEK
        return data["low"].astype(float).rolling(window, min_periods=window).min()
    raise ValueError(f"unsupported indicator: {indicator}")


_TRADING_DAYS_PER_WEEK = 5


def _consecutive_streak(close: pd.Series, rising: bool) -> pd.Series:
    """Count consecutive days closing higher (rising=True) or lower (rising=False)
    than the prior close, resetting to 0 on any day that breaks the streak."""
    change = close.diff()
    matches = change > 0 if rising else change < 0
    reset_groups = (~matches).cumsum()
    return matches.astype(int).groupby(reset_groups).cumsum().astype(float)
