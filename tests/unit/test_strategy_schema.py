from datetime import date

import pytest
from pydantic import ValidationError

from services.api.app.schemas.strategy_schema import Strategy


def valid_strategy() -> dict:
    indicator = {"type": "INDICATOR", "indicator": "SMA", "period": 5}
    return {
        "strategy_name": "Sample SMA strategy",
        "universe": {"symbols": ["005930"]},
        "period": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
        "entry_rules": {"conditions": [{"left": indicator, "operator": "CROSS_ABOVE", "right": {"indicator": "EMA", "period": 10}}]},
        "exit_rules": {"conditions": [{"left": indicator, "operator": "CROSS_BELOW", "right": {"indicator": "EMA", "period": 10}}]},
        "position_sizing": {"method": "PERCENT_OF_EQUITY", "value": 0.5},
        "capital": {"initial_cash": 10_000_000},
    }


def test_strategy_schema_accepts_readme_shape():
    strategy = Strategy.model_validate(valid_strategy())
    assert strategy.period.start_date == date(2024, 1, 1)
    assert strategy.execution.execution_time == "NEXT_OPEN"


def test_strategy_schema_rejects_reversed_period():
    payload = valid_strategy()
    payload["period"] = {"start_date": "2025-01-01", "end_date": "2024-01-01"}
    with pytest.raises(ValidationError):
        Strategy.model_validate(payload)


def test_strategy_schema_rejects_indicator_without_period():
    payload = valid_strategy()
    payload["entry_rules"]["conditions"][0]["left"] = {"indicator": "RSI"}
    with pytest.raises(ValidationError):
        Strategy.model_validate(payload)


def test_indicator_reference_normalizes_symbol_to_uppercase():
    payload = valid_strategy()
    payload["entry_rules"]["conditions"][0]["left"] = {"indicator": "RETURN", "symbol": "kospi"}
    strategy = Strategy.model_validate(payload)
    assert strategy.entry_rules.conditions[0].left.symbol == "KOSPI"


def test_signal_symbols_excludes_traded_symbol_and_unset_operands():
    payload = valid_strategy()
    payload["entry_rules"]["conditions"][0]["left"] = {"indicator": "RETURN", "symbol": "KOSPI"}
    payload["entry_rules"]["conditions"][0]["right"] = {"indicator": "EMA", "period": 10, "symbol": "005930"}
    strategy = Strategy.model_validate(payload)
    assert strategy.signal_symbols() == {"KOSPI"}


def test_signal_symbols_empty_when_no_condition_sets_symbol():
    strategy = Strategy.model_validate(valid_strategy())
    assert strategy.signal_symbols() == set()
