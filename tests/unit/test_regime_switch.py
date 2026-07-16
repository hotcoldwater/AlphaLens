from datetime import date

import pandas as pd
import pytest
from pydantic import ValidationError

from services.api.app.backtest_engine.regime_switch import run_regime_switch_backtest
from services.api.app.schemas.backtest_schema import BacktestRequest, OHLCVBar
from services.api.app.schemas.strategy_schema import RegimeSwitchStrategy


def regime_strategy() -> RegimeSwitchStrategy:
    return RegimeSwitchStrategy.model_validate(
        {
            "strategy_type": "REGIME_SWITCH",
            "strategy_name": "SPY defensive GLD switch",
            "market": "NASDAQ",
            "universe": {"type": "REGIME_SWITCH", "symbols": ["SPY", "GLD"]},
            "period": {"start_date": "2024-01-02", "end_date": "2024-01-05"},
            "default_symbol": "SPY",
            "switch_rule": {
                "signal_symbol": "SPY",
                "condition": {
                    "left": {"indicator": "CLOSE"},
                    "operator": "LESS_THAN",
                    "right": {"indicator": "SMA", "period": 2},
                },
                "target_symbol": "GLD",
            },
            "capital": {"initial_cash": 1000, "currency": "USD"},
        }
    )


def frame(values: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-02", periods=len(values), freq="D")
    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 1 for value in values],
            "low": [value - 1 for value in values],
            "close": values,
            "volume": [1000] * len(values),
        },
        index=dates,
    )


def test_regime_switch_moves_from_default_to_defensive_asset_next_open():
    result = run_regime_switch_backtest(
        {"SPY": frame([100, 90, 110, 120]), "GLD": frame([50, 50, 50, 50])},
        regime_strategy(),
    )

    # SPY's second close is below its two-day SMA, so GLD is entered on day three.
    assert result.trades[0].symbol == "SPY"
    assert result.trades[0].exit_date.date() == date(2024, 1, 4)
    assert result.trades[1].symbol == "GLD"
    assert result.trades[1].entry_date.date() == date(2024, 1, 4)
    assert result.trades[1].exit_date.date() == date(2024, 1, 5)


def test_regime_switch_rejects_missing_symbol_data():
    strategy = regime_strategy()
    bar = OHLCVBar(date="2024-01-02", open=100, high=101, low=99, close=100, volume=1000)

    with pytest.raises(ValidationError, match="data_by_symbol"):
        BacktestRequest(strategy=strategy, data_by_symbol={"SPY": [bar]})


def test_regime_switch_rejects_target_outside_universe():
    payload = regime_strategy().model_dump(mode="json")
    payload["switch_rule"]["target_symbol"] = "TLT"

    with pytest.raises(ValidationError, match="target_symbol"):
        RegimeSwitchStrategy.model_validate(payload)
