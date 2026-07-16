import pandas as pd
import pytest

from services.api.app.backtest_engine.indicators import ema, rsi, sma


def test_sma_uses_only_completed_window():
    result = sma(pd.Series([1, 2, 3, 4, 5]), 3)
    pd.testing.assert_series_equal(result, pd.Series([float("nan"), float("nan"), 2.0, 3.0, 4.0]))


def test_ema_returns_expected_values():
    result = ema(pd.Series([10, 20, 30, 40]), 3)
    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx(22.5)
    assert result.iloc[3] == pytest.approx(31.25)


def test_rsi_detects_gain_and_loss():
    result = rsi(pd.Series([1, 2, 3, 2, 2, 3]), 3)
    assert result.iloc[:3].isna().all()
    assert result.iloc[3] == pytest.approx(66.6666667)


@pytest.mark.parametrize("function", [sma, ema, rsi])
def test_indicators_reject_invalid_period(function):
    with pytest.raises(ValueError):
        function(pd.Series([1, 2, 3]), 0)
