import pandas as pd
import pytest

from services.api.app.backtest_engine.engine import run_backtest
from tests.unit.test_strategy_schema import valid_strategy
from services.api.app.schemas.strategy_schema import Strategy


def strategy_with_costs() -> Strategy:
    payload = valid_strategy()
    payload["capital"] = {"initial_cash": 1_000}
    payload["position_sizing"] = {"method": "AVAILABLE_CASH"}
    payload["costs"] = {"commission_rate": 0.01, "slippage_rate": 0.1, "tax_rate": 0.02}
    return Strategy.model_validate(payload)


def test_signal_is_filled_at_next_open_and_costs_are_applied():
    data = pd.DataFrame(
        {"open": [10, 20, 30, 40], "close": [10, 20, 30, 40]},
        index=pd.date_range("2024-01-01", periods=4),
    )
    entry = pd.Series([True, False, False, False], index=data.index)
    exit = pd.Series([False, False, True, False], index=data.index)

    result = run_backtest(data, entry, exit, strategy_with_costs())

    assert result.trade_count == 1
    trade = result.trades[0]
    assert trade.entry_date == data.index[1]
    assert trade.exit_date == data.index[3]
    assert trade.quantity == 45
    assert trade.holding_days == 2
    assert trade.entry_cost == pytest.approx(9.9)
    assert trade.exit_cost == pytest.approx(48.6)
    assert result.total_cost == pytest.approx(58.5)
    assert result.win_rate == 1.0
    assert result.final_equity == pytest.approx(1_571.5)


def test_last_day_signal_is_not_executed():
    data = pd.DataFrame(
        {"open": [10, 20], "close": [10, 20]},
        index=pd.date_range("2024-01-01", periods=2),
    )
    signal = pd.Series([False, True], index=data.index)
    result = run_backtest(data, signal, signal, strategy_with_costs())
    assert result.trade_count == 0
    assert result.final_equity == 1_000


def test_metrics_and_repeated_runs_are_reproducible():
    data = pd.DataFrame(
        {"open": [10, 10, 20, 20], "close": [10, 10, 20, 20]},
        index=pd.date_range("2024-01-01", periods=4),
    )
    entry = pd.Series([True, False, False, False], index=data.index)
    exit = pd.Series([False, False, True, False], index=data.index)
    strategy = Strategy.model_validate({**valid_strategy(), "capital": {"initial_cash": 100}, "position_sizing": {"method": "AVAILABLE_CASH"}})

    first = run_backtest(data, entry, exit, strategy)
    second = run_backtest(data, entry, exit, strategy)

    assert first.total_return == pytest.approx(1.0)
    assert first.max_drawdown == pytest.approx(0.0)
    assert first.as_dict() == second.as_dict()
