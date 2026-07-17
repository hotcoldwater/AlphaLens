from services.api.app.schemas.backtest_schema import BacktestRequest, OHLCVBar
from services.api.app.schemas.strategy_schema import Strategy
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
