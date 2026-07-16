import pandas as pd


def _validate_period(period: int) -> None:
    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ValueError("period must be a positive integer")


def sma(values: pd.Series, period: int) -> pd.Series:
    _validate_period(period)
    return values.rolling(window=period, min_periods=period).mean()


def ema(values: pd.Series, period: int) -> pd.Series:
    _validate_period(period)
    return values.ewm(span=period, adjust=False, min_periods=period).mean()


def rsi(values: pd.Series, period: int = 14) -> pd.Series:
    _validate_period(period)
    delta = values.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    average_gain = gains.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    average_loss = losses.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    relative_strength = average_gain / average_loss
    result = 100 - (100 / (1 + relative_strength))
    result = result.mask((average_loss == 0) & (average_gain > 0), 100)
    return result.mask((average_gain == 0) & (average_loss == 0), 0)
