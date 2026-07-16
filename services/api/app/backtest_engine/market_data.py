import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {"open", "high", "low", "close", "volume"}
VERSION_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class DataVersion:
    """A reproducible identifier for the validated OHLCV data used by a run."""

    identifier: str
    start_date: str
    end_date: str
    point_count: int


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        data = pd.read_csv(path)
    elif path.suffix.lower() == ".parquet":
        try:
            data = pd.read_parquet(path)
        except ImportError as error:
            raise ValueError(
                "Parquet support requires the optional requirements-parquet.txt dependencies"
            ) from error
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


def build_data_version(data: pd.DataFrame) -> DataVersion:
    """Fingerprint normalized OHLCV input so a run can identify its exact data."""
    validated = validate_ohlcv(data)
    records = [
        [
            index.isoformat(),
            *[float(row[column]) for column in VERSION_COLUMNS],
        ]
        for index, row in validated.loc[:, list(VERSION_COLUMNS)].iterrows()
    ]
    payload = json.dumps(records, ensure_ascii=True, separators=(",", ":"))
    return DataVersion(
        identifier=f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}",
        start_date=validated.index[0].date().isoformat(),
        end_date=validated.index[-1].date().isoformat(),
        point_count=len(validated),
    )


def build_multi_asset_data_version(data_by_symbol: dict[str, pd.DataFrame]) -> DataVersion:
    """Fingerprint every aligned asset so regime-switch runs remain reproducible."""
    normalized = {symbol.upper(): validate_ohlcv(data) for symbol, data in data_by_symbol.items()}
    records = {
        symbol: [
            [index.isoformat(), *[float(row[column]) for column in VERSION_COLUMNS]]
            for index, row in data.loc[:, list(VERSION_COLUMNS)].iterrows()
        ]
        for symbol, data in sorted(normalized.items())
    }
    payload = json.dumps(records, ensure_ascii=True, separators=(",", ":"))
    all_indexes = [data.index for data in normalized.values()]
    common_index = all_indexes[0]
    for index in all_indexes[1:]:
        common_index = common_index.intersection(index)
    if common_index.empty:
        raise ValueError("no common market data dates across strategy symbols")
    return DataVersion(
        identifier=f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}",
        start_date=common_index.min().date().isoformat(),
        end_date=common_index.max().date().isoformat(),
        point_count=len(common_index),
    )
