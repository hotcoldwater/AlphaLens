import pytest

from services.api.app.schemas.backtest_schema import BacktestRequest, OHLCVBar
from services.api.app.schemas.strategy_schema import AllocationRebalanceStrategy, Strategy
from services.api.app.services.backtest_service import execute_backtest
from tests.unit.test_strategy_schema import valid_strategy


def _bars(dates: list[str], closes: list[float]) -> list[OHLCVBar]:
    return [
        OHLCVBar(date=date, open=close, high=close + 1, low=close - 1, close=close, volume=1000)
        for date, close in zip(dates, closes)
    ]


def test_cross_asset_condition_is_driven_by_signal_symbol_not_traded_symbol():
    dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    # Samsung's own daily return is always positive, so if the engine incorrectly
    # fell back to evaluating the condition against Samsung's own data, the
    # RETURN < 0 entry condition below would never fire.
    samsung_closes = [100, 101, 102, 103, 104]
    # KOSPI alternates down/up, which should drive entry/exit instead.
    kospi_closes = [1000, 990, 1000, 990, 1000]

    payload = valid_strategy()
    payload["period"] = {"start_date": "2024-01-01", "end_date": "2024-01-05"}
    payload["position_sizing"] = {"method": "AVAILABLE_CASH"}
    payload["entry_rules"] = {
        "conditions": [
            {"left": {"indicator": "RETURN", "period": 1, "symbol": "KOSPI"}, "operator": "LESS_THAN", "right": {"value": 0}}
        ]
    }
    payload["exit_rules"] = {
        "conditions": [
            {"left": {"indicator": "RETURN", "period": 1, "symbol": "KOSPI"}, "operator": "GREATER_THAN", "right": {"value": 0}}
        ]
    }
    strategy = Strategy.model_validate(payload)
    assert strategy.signal_symbols() == {"KOSPI"}

    request = BacktestRequest(
        strategy=strategy,
        data=_bars(dates, samsung_closes),
        data_by_symbol={"KOSPI": _bars(dates, kospi_closes)},
    )

    execution = execute_backtest(request)

    assert execution.result.trade_count >= 1
    assert execution.result.trades[0].symbol == "005930"


def test_macro_ticker_signal_symbol_with_special_characters_is_accepted():
    """FX/futures/rate tickers like KRW=X or ^TNX contain characters ('=', '^')
    that don't appear in stock/index tickers -- confirm the schema, engine, and
    data alignment all handle them the same as any other signal symbol."""
    dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    samsung_closes = [100, 101, 102, 103, 104]
    fx_closes = [1300, 1290, 1300, 1290, 1300]

    payload = valid_strategy()
    payload["period"] = {"start_date": "2024-01-01", "end_date": "2024-01-05"}
    payload["position_sizing"] = {"method": "AVAILABLE_CASH"}
    payload["entry_rules"] = {
        "conditions": [
            {"left": {"indicator": "RETURN", "period": 1, "symbol": "KRW=X"}, "operator": "LESS_THAN", "right": {"value": 0}}
        ]
    }
    payload["exit_rules"] = {
        "conditions": [
            {"left": {"indicator": "RETURN", "period": 1, "symbol": "KRW=X"}, "operator": "GREATER_THAN", "right": {"value": 0}}
        ]
    }
    strategy = Strategy.model_validate(payload)
    assert strategy.signal_symbols() == {"KRW=X"}

    request = BacktestRequest(
        strategy=strategy,
        data=_bars(dates, samsung_closes),
        data_by_symbol={"KRW=X": _bars(dates, fx_closes)},
    )

    execution = execute_backtest(request)

    assert execution.result.trade_count >= 1


def test_backtest_request_rejects_missing_signal_symbol_data():
    payload = valid_strategy()
    payload["entry_rules"]["conditions"][0]["left"] = {"indicator": "RETURN", "period": 1, "symbol": "KOSPI"}
    strategy = Strategy.model_validate(payload)

    dates = ["2024-01-01", "2024-01-02"]
    closes = [100, 101]
    try:
        BacktestRequest(strategy=strategy, data=_bars(dates, closes))
        assert False, "expected a validation error for missing signal data"
    except Exception as error:
        assert "KOSPI" in str(error)


def allocation_strategy_for_service() -> AllocationRebalanceStrategy:
    return AllocationRebalanceStrategy.model_validate({
        "strategy_type": "ALLOCATION_REBALANCE",
        "strategy_name": "60/40 portfolio",
        "market": "NASDAQ",
        "universe": {"type": "ALLOCATION_REBALANCE", "symbols": ["SPY", "GLD"]},
        "period": {"start_date": "2024-01-01", "end_date": "2024-01-31"},
        "target_allocations": [
            {"symbol": "SPY", "weight": 0.6},
            {"symbol": "GLD", "weight": 0.4},
        ],
        "capital": {"initial_cash": 1000, "currency": "USD"},
    })


def test_allocation_rebalance_rejects_symbol_data_that_ends_early():
    strategy = allocation_strategy_for_service()
    dates = [f"2024-01-{day:02d}" for day in range(1, 32)]
    # GLD's feed stops on Jan 10, 21 days before the requested period end (Jan 31)
    # -- far more than an ordinary holiday gap, so this should read as a delisting.
    gld_dates = [f"2024-01-{day:02d}" for day in range(1, 11)]

    request = BacktestRequest(
        strategy=strategy,
        data_by_symbol={
            "SPY": _bars(dates, [100.0] * len(dates)),
            "GLD": _bars(gld_dates, [50.0] * len(gld_dates)),
        },
    )

    with pytest.raises(ValueError, match="GLD.*상장폐지"):
        execute_backtest(request)
