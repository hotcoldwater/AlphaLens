from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        data = pd.read_csv(path)
    elif path.suffix.lower() == ".parquet":
        data = pd.read_parquet(path)
    else:
        raise ValueError("market data must be a .csv or .parquet file")

    date_column = next((name for name in ("date", "datetime") if name in data.columns), None)
    if date_column is None:
        raise ValueError("market data must contain date or datetime column")
    data = data.rename(columns=str.lower)
    date_column = date_column.lower()
    data[date_column] = pd.to_datetime(data[date_column], errors="raise")
    data = data.set_index(date_column)
    return validate_ohlcv(data)


def validate_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    normalized = data.rename(columns=str.lower).copy()
    missing = REQUIRED_COLUMNS - set(normalized.columns)
    if missing:
        raise ValueError(f"missing OHLCV columns: {sorted(missing)}")
    if not isinstance(normalized.index, pd.DatetimeIndex):
        raise ValueError("OHLCV index must be a DatetimeIndex")
    if normalized.empty:
        raise ValueError("OHLCV data must not be empty")
    if not normalized.index.is_monotonic_increasing or not normalized.index.is_unique:
        raise ValueError("OHLCV dates must be sorted and unique")
    values = normalized[list(REQUIRED_COLUMNS)].apply(pd.to_numeric, errors="raise")
    if values.isna().any().any() or not values.map(lambda value: pd.notna(value) and pd.api.types.is_number(value)).all().all():
        raise ValueError("OHLCV data must contain finite numeric values")
    if (values[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (values["volume"] < 0).any():
        raise ValueError("volume must not be negative")
    if (values["high"] < values[["open", "low", "close"]].max(axis=1)).any():
        raise ValueError("high must be at least open, low, and close")
    if (values["low"] > values[["open", "high", "close"]].min(axis=1)).any():
        raise ValueError("low must be at most open, high, and close")
    normalized[list(REQUIRED_COLUMNS)] = values
    return normalized.sort_index()
