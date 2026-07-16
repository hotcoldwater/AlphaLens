import pandas as pd


def sample_ohlcv() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    close = [100, 99, 98, 99, 101, 103, 102, 100, 98, 99, 101, 104]
    return pd.DataFrame(
        {
            "open": [value - 1 for value in close],
            "high": [value + 1 for value in close],
            "low": [value - 2 for value in close],
            "close": close,
            "volume": [1000 + index * 100 for index in range(len(close))],
        },
        index=dates,
    )
