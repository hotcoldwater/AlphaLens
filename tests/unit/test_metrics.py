import pandas as pd

from services.api.app.backtest_engine.metrics import annualized_volatility, sharpe_ratio


def test_metrics_are_zero_when_no_returns_exist():
    equity = pd.Series([100.0], index=pd.date_range("2024-01-01", periods=1))
    assert annualized_volatility(equity) == 0.0
    assert sharpe_ratio(equity) == 0.0


def test_metrics_are_calculated_from_daily_equity_returns():
    equity = pd.Series(
        [100.0, 101.0, 100.0, 102.0],
        index=pd.date_range("2024-01-01", periods=4),
    )
    assert annualized_volatility(equity) > 0
    assert sharpe_ratio(equity) > 0
