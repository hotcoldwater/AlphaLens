import pandas as pd
import pytest

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


def test_condition_with_symbol_reads_from_signal_data_not_primary_data():
    from services.api.app.schemas.strategy_schema import Condition

    data = sample_ohlcv()
    signal_frame = data.copy()
    signal_frame["close"] = 0.0  # signal symbol never trades above 0

    condition = Condition.model_validate(
        {"left": {"indicator": "CLOSE", "symbol": "KOSPI"}, "operator": "GREATER_THAN", "right": {"value": 0}}
    )
    result = evaluate_condition(data, condition, signal_data={"KOSPI": signal_frame})
    assert not result.any()

    # Without signal_data, the operand.symbol is ignored and the primary frame is used.
    fallback = evaluate_condition(data, condition)
    assert fallback.any()


def test_day_of_week_and_month_of_year_indicators():
    from services.api.app.schemas.strategy_schema import Condition

    data = sample_ohlcv()  # 2024-01-01 (Monday) through 2024-01-12
    monday = Condition.model_validate(
        {"left": {"indicator": "DAY_OF_WEEK"}, "operator": "EQUAL", "right": {"value": 0}}
    )
    assert evaluate_condition(data, monday).sum() == 2  # 2024-01-01 and 2024-01-08

    january = Condition.model_validate(
        {"left": {"indicator": "MONTH_OF_YEAR"}, "operator": "EQUAL", "right": {"value": 1}}
    )
    assert evaluate_condition(data, january).sum() == len(data)


def test_consecutive_up_and_down_day_streaks():
    from services.api.app.schemas.strategy_schema import Condition

    data = sample_ohlcv()  # close: 100 99 98 99 101 103 102 100 98 99 101 104
    up_streak = Condition.model_validate(
        {"left": {"indicator": "CONSECUTIVE_UP_DAYS"}, "operator": "GREATER_THAN_OR_EQUAL", "right": {"value": 3}}
    )
    result = evaluate_condition(data, up_streak)
    assert result.sum() == 2
    assert result.iloc[5] and result.iloc[11]

    down_streak = Condition.model_validate(
        {"left": {"indicator": "CONSECUTIVE_DOWN_DAYS"}, "operator": "GREATER_THAN_OR_EQUAL", "right": {"value": 2}}
    )
    result = evaluate_condition(data, down_streak)
    assert result.sum() == 3
    assert result.iloc[2] and result.iloc[7] and result.iloc[8]


def test_gap_return_indicator():
    from services.api.app.schemas.strategy_schema import Condition

    data = sample_ohlcv()  # open == close - 1 by construction
    gap_down = Condition.model_validate(
        {"left": {"indicator": "GAP_RETURN"}, "operator": "LESS_THAN", "right": {"value": 0}}
    )
    result = evaluate_condition(data, gap_down)
    assert result.sum() == 5
    assert not result.iloc[0]  # no prior close on the first day


def test_n_week_high_and_low_use_a_five_trading_day_week():
    from services.api.app.schemas.strategy_schema import Condition

    data = sample_ohlcv()  # high: 101 100 99 100 102 104 103 101 99 100 102 105
    condition = Condition.model_validate(
        {"left": {"indicator": "N_WEEK_HIGH", "period": 1}, "operator": "EQUAL", "right": {"indicator": "HIGH"}}
    )
    result = evaluate_condition(data, condition)
    assert not result.iloc[:4].any()  # fewer than 5 trading days of history
    assert result.iloc[5]  # 104 is the rolling 5-day high and today's high


def test_condition_with_unknown_signal_symbol_raises():
    from services.api.app.schemas.strategy_schema import Condition

    data = sample_ohlcv()
    condition = Condition.model_validate(
        {"left": {"indicator": "CLOSE", "symbol": "KOSPI"}, "operator": "GREATER_THAN", "right": {"value": 0}}
    )
    with pytest.raises(ValueError, match="missing signal data for KOSPI"):
        evaluate_condition(data, condition, signal_data={})
