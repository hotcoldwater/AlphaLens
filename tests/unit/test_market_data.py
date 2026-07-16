import pandas as pd
import pytest

from services.api.app.backtest_engine.market_data import load_ohlcv, validate_ohlcv
from tests.fixtures.sample_ohlcv import sample_ohlcv


def test_load_ohlcv_csv(tmp_path):
    path = tmp_path / "sample.csv"
    sample_ohlcv().rename_axis("date").reset_index().to_csv(path, index=False)

    loaded = load_ohlcv(path)

    expected = sample_ohlcv().rename_axis("date")
    expected.index.freq = None
    pd.testing.assert_frame_equal(loaded, expected)


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data.rename(columns={"volume": "shares"}),
        lambda data: data.assign(volume=-1),
        lambda data: data.assign(high=0),
    ],
)
def test_validate_ohlcv_rejects_invalid_data(change):
    with pytest.raises(ValueError):
        validate_ohlcv(change(sample_ohlcv()))


def test_validate_ohlcv_rejects_duplicate_dates():
    data = sample_ohlcv()
    data.index = [data.index[0]] * len(data)
    with pytest.raises(ValueError, match="sorted and unique"):
        validate_ohlcv(data)
