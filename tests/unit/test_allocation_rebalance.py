import pandas as pd
import pytest
from pydantic import ValidationError

from services.api.app.backtest_engine.allocation_rebalance import run_allocation_rebalance_backtest
from services.api.app.schemas.strategy_schema import AllocationRebalanceStrategy


def allocation_strategy(
    frequency: str = "MONTHLY", start_date: str = "2024-01-31", end_date: str = "2024-02-02"
) -> AllocationRebalanceStrategy:
    return AllocationRebalanceStrategy.model_validate(
        {
            "strategy_type": "ALLOCATION_REBALANCE",
            "strategy_name": "60/40 monthly portfolio",
            "market": "NASDAQ",
            "universe": {"type": "ALLOCATION_REBALANCE", "symbols": ["SPY", "GLD"]},
            "period": {"start_date": start_date, "end_date": end_date},
            "target_allocations": [
                {"symbol": "SPY", "weight": 0.6},
                {"symbol": "GLD", "weight": 0.4},
            ],
            "rebalance": {"frequency": frequency},
            "capital": {"initial_cash": 1000, "currency": "USD"},
        }
    )


def frame(values: list[float], dates: list[str] | None = None) -> pd.DataFrame:
    index = pd.to_datetime(dates or ["2024-01-31", "2024-02-01", "2024-02-02"])
    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 1 for value in values],
            "low": [value - 1 for value in values],
            "close": values,
            "volume": [1000] * len(values),
        },
        index=index,
    )


def test_monthly_rebalance_sells_excess_before_buying_deficit():
    result = run_allocation_rebalance_backtest(
        {"SPY": frame([100, 200, 200]), "GLD": frame([100, 50, 50])},
        allocation_strategy(),
    )

    assert result.trades[0].symbol == "SPY"
    assert result.trades[0].quantity == 2
    assert result.trades[0].exit_date.date().isoformat() == "2024-02-01"
    assert result.total_cost == 0
    assert result.final_equity == 1400


def test_weekly_rebalance_triggers_on_new_iso_week():
    dates = ["2024-01-26", "2024-01-29", "2024-01-30"]  # Fri (wk4), Mon (wk5), Tue (wk5)
    result = run_allocation_rebalance_backtest(
        {
            "SPY": frame([100, 200, 200], dates),
            "GLD": frame([100, 50, 50], dates),
        },
        allocation_strategy("WEEKLY", start_date="2024-01-26", end_date="2024-01-30"),
    )

    assert result.trades[0].symbol == "SPY"
    assert result.trades[0].exit_date.date().isoformat() == "2024-01-29"
    assert result.final_equity == 1400


def test_quarterly_rebalance_triggers_on_new_quarter():
    dates = ["2024-03-29", "2024-04-01", "2024-04-02"]  # Q1, Q2, Q2
    result = run_allocation_rebalance_backtest(
        {
            "SPY": frame([100, 200, 200], dates),
            "GLD": frame([100, 50, 50], dates),
        },
        allocation_strategy("QUARTERLY", start_date="2024-03-29", end_date="2024-04-02"),
    )

    assert result.trades[0].symbol == "SPY"
    assert result.trades[0].exit_date.date().isoformat() == "2024-04-01"
    assert result.final_equity == 1400


def test_allocation_schema_allows_cash_residual_but_rejects_overallocation():
    payload = allocation_strategy().model_dump(mode="json")
    payload["target_allocations"][1]["weight"] = 0.2
    strategy = AllocationRebalanceStrategy.model_validate(payload)
    assert sum(item.weight for item in strategy.target_allocations) == 0.8

    payload["target_allocations"][1]["weight"] = 0.5
    with pytest.raises(ValidationError, match="sum to 1 or less"):
        AllocationRebalanceStrategy.model_validate(payload)


def test_allocation_rebalance_reports_common_date_shortage_with_symbol_counts():
    spy = frame([100, 101, 102])
    gld = frame([50, 51, 52])
    gld.index = pd.to_datetime(["2024-02-02", "2024-02-03", "2024-02-04"])

    with pytest.raises(ValueError, match=r"found 1; supplied data points — SPY: 3개, GLD: 3개"):
        run_allocation_rebalance_backtest({"SPY": spy, "GLD": gld}, allocation_strategy())
