import pandas as pd

from services.api.app.backtest_engine.metrics import (
    annualized_volatility,
    buy_and_hold_equity_curve,
    maximum_drawdown,
    sharpe_ratio,
)


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


def test_buy_and_hold_reference_curve_and_drawdown():
    close = pd.Series([100.0, 120.0, 90.0, 110.0], index=pd.date_range("2024-01-01", periods=4))

    curve = buy_and_hold_equity_curve(close, 1_000)

    assert curve.tolist() == [1_000, 1_200, 900, 1_100]
    assert maximum_drawdown(curve) == -0.25
