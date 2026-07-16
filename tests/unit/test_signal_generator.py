import pandas as pd

from services.api.app.backtest_engine.signal_generator import (
    evaluate_condition,
    evaluate_rules,
    generate_strategy_signals,
)
from services.api.app.enums import LogicType
from services.api.app.schemas.strategy_schema import Strategy
from tests.fixtures.sample_ohlcv import sample_ohlcv
from tests.unit.test_strategy_schema import valid_strategy


def test_comparison_and_cross_conditions_use_strategy_schema():
    data = sample_ohlcv()
    condition = {
        "left": {"indicator": "CLOSE"},
        "operator": "CROSS_ABOVE",
        "right": {"type": "VALUE", "value": 100},
    }
    strategy = Strategy.model_validate(
        {
            **valid_strategy(),
            "entry_rules": {"conditions": [condition]},
            "exit_rules": {"conditions": [{**condition, "operator": "CROSS_BELOW"}]},
        }
    )

    entry, exit = generate_strategy_signals(data, strategy)

    assert entry["2024-01-05"]
    assert exit["2024-01-02"]
    assert entry.sum() == 2
    assert exit.sum() == 2


def test_and_and_or_logic_combine_conditions():
    data = sample_ohlcv()
    rules = {
        "logic": LogicType.AND,
        "conditions": [
            {"left": {"indicator": "CLOSE"}, "operator": "GREATER_THAN", "right": {"value": 100}},
            {"left": {"indicator": "VOLUME"}, "operator": "GREATER_THAN", "right": {"value": 1000}},
        ],
    }
    from services.api.app.schemas.strategy_schema import RuleSet

    assert evaluate_rules(data, RuleSet.model_validate(rules)).sum() == 5
    rules["logic"] = LogicType.OR
    assert evaluate_rules(data, RuleSet.model_validate(rules)).sum() == 11


def test_indicator_with_insufficient_history_is_false():
    data = sample_ohlcv()
    from services.api.app.schemas.strategy_schema import Condition

    condition = Condition.model_validate(
        {"left": {"indicator": "SMA", "period": 20}, "operator": "GREATER_THAN", "right": {"value": 0}}
    )
    assert not evaluate_condition(data, condition).any()
