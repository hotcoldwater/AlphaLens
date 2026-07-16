from datetime import date
from typing import Annotated, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..enums import (
    DataTimeframe,
    ExecutionTime,
    IndicatorType,
    LogicType,
    OperatorType,
    PositionSizingMethod,
    RebalanceFrequency,
    SignalTime,
    UniverseType,
)

PositivePeriod = Annotated[int, Field(ge=1)]


class IndicatorReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(default="INDICATOR", pattern="^INDICATOR$")
    indicator: IndicatorType
    period: PositivePeriod | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "IndicatorReference":
        needs_period = self.indicator in {
            IndicatorType.SMA, IndicatorType.EMA, IndicatorType.RSI,
            IndicatorType.N_DAY_RETURN, IndicatorType.N_DAY_HIGH,
            IndicatorType.N_DAY_LOW, IndicatorType.VOLUME_SMA,
        }
        if needs_period and self.period is None:
            raise ValueError(f"{self.indicator} requires period")
        return self


class ValueReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(default="VALUE", pattern="^VALUE$")
    value: float


Operand = Union[IndicatorReference, ValueReference]


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: Operand
    operator: OperatorType
    right: Operand


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logic: LogicType = LogicType.AND
    conditions: Annotated[list[Condition], Field(min_length=1)]


class Universe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: UniverseType = UniverseType.SINGLE_STOCK
    symbols: Annotated[list[str], Field(min_length=1, max_length=1)]


class SwitchUniverse(BaseModel):
    """A deliberately limited, two-asset universe for full allocation switches."""

    model_config = ConfigDict(extra="forbid")
    type: UniverseType = UniverseType.REGIME_SWITCH
    symbols: Annotated[list[str], Field(min_length=2, max_length=2)]

    @model_validator(mode="after")
    def validate_distinct_symbols(self) -> "SwitchUniverse":
        normalized = [symbol.upper() for symbol in self.symbols]
        if len(set(normalized)) != 2:
            raise ValueError("REGIME_SWITCH requires two distinct symbols")
        self.symbols = normalized
        return self


class AllocationUniverse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: UniverseType = UniverseType.ALLOCATION_REBALANCE
    symbols: Annotated[list[str], Field(min_length=2, max_length=5)]

    @model_validator(mode="after")
    def validate_distinct_symbols(self) -> "AllocationUniverse":
        self.symbols = [symbol.upper() for symbol in self.symbols]
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("ALLOCATION_REBALANCE requires distinct symbols")
        return self


class Period(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_order(self) -> "Period":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timeframe: DataTimeframe = DataTimeframe.DAILY
    adjusted_price: bool = True


class PositionSizing(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: PositionSizingMethod
    value: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_value(self) -> "PositionSizing":
        if self.method == PositionSizingMethod.AVAILABLE_CASH and self.value is not None:
            raise ValueError("AVAILABLE_CASH does not accept value")
        if self.method == PositionSizingMethod.PERCENT_OF_EQUITY and (self.value is None or self.value > 1):
            raise ValueError("PERCENT_OF_EQUITY value must be between 0 and 1")
        if self.method != PositionSizingMethod.AVAILABLE_CASH and self.value is None:
            raise ValueError(f"{self.method} requires value")
        return self


class RiskManagement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stop_loss: float | None = Field(default=None, gt=0, le=1)
    take_profit: float | None = Field(default=None, gt=0)
    maximum_holding_days: PositivePeriod | None = None


class ExecutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signal_time: SignalTime = SignalTime.CLOSE
    execution_time: ExecutionTime = ExecutionTime.NEXT_OPEN


class Costs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commission_rate: float = Field(default=0, ge=0)
    slippage_rate: float = Field(default=0, ge=0)
    tax_rate: float = Field(default=0, ge=0)


class Capital(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_cash: float = Field(gt=0)
    currency: str = "KRW"


class Strategy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_type: str = Field(default="SINGLE_STOCK", pattern="^SINGLE_STOCK$")
    strategy_name: str = Field(min_length=1)
    market: str = "KRX"
    universe: Universe
    period: Period
    data: DataConfig = DataConfig()
    entry_rules: RuleSet
    exit_rules: RuleSet
    position_sizing: PositionSizing
    risk_management: RiskManagement = RiskManagement()
    execution: ExecutionConfig = ExecutionConfig()
    costs: Costs = Costs()
    capital: Capital
    benchmark: str | None = None


class RegimeSwitchRule(BaseModel):
    """When the signal is true, move the full portfolio to target_symbol."""

    model_config = ConfigDict(extra="forbid")
    signal_symbol: str = Field(min_length=1, max_length=32)
    condition: Condition
    target_symbol: str = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def normalize_symbols(self) -> "RegimeSwitchRule":
        self.signal_symbol = self.signal_symbol.upper()
        self.target_symbol = self.target_symbol.upper()
        return self


class RegimeSwitchStrategy(BaseModel):
    """Two-asset, long-only, full-allocation regime switching strategy.

    The default asset is held unless the signal condition is true. Conditions are
    evaluated using signal_symbol at the close and filled at the next common open.
    """

    model_config = ConfigDict(extra="forbid")
    strategy_type: str = Field(default="REGIME_SWITCH", pattern="^REGIME_SWITCH$")
    strategy_name: str = Field(min_length=1)
    market: str = "NASDAQ"
    universe: SwitchUniverse
    period: Period
    data: DataConfig = DataConfig()
    default_symbol: str = Field(min_length=1, max_length=32)
    switch_rule: RegimeSwitchRule
    execution: ExecutionConfig = ExecutionConfig()
    costs: Costs = Costs()
    capital: Capital
    benchmark: str | None = None

    @model_validator(mode="after")
    def validate_symbols(self) -> "RegimeSwitchStrategy":
        symbols = set(self.universe.symbols)
        self.default_symbol = self.default_symbol.upper()
        if self.default_symbol not in symbols:
            raise ValueError("default_symbol must be in universe.symbols")
        if self.switch_rule.signal_symbol not in symbols:
            raise ValueError("switch_rule.signal_symbol must be in universe.symbols")
        if self.switch_rule.target_symbol not in symbols:
            raise ValueError("switch_rule.target_symbol must be in universe.symbols")
        if self.switch_rule.target_symbol == self.default_symbol:
            raise ValueError("switch_rule.target_symbol must differ from default_symbol")
        return self


class TargetAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=32)
    weight: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def normalize_symbol(self) -> "TargetAllocation":
        self.symbol = self.symbol.upper()
        return self


class RebalanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frequency: RebalanceFrequency = RebalanceFrequency.MONTHLY


class AllocationRebalanceStrategy(BaseModel):
    """Long-only fixed target weights, rebalanced at the first common session monthly."""

    model_config = ConfigDict(extra="forbid")
    strategy_type: str = Field(default="ALLOCATION_REBALANCE", pattern="^ALLOCATION_REBALANCE$")
    strategy_name: str = Field(min_length=1)
    market: str = "NASDAQ"
    universe: AllocationUniverse
    period: Period
    data: DataConfig = DataConfig()
    target_allocations: Annotated[list[TargetAllocation], Field(min_length=2, max_length=5)]
    rebalance: RebalanceConfig = RebalanceConfig()
    execution: ExecutionConfig = ExecutionConfig()
    costs: Costs = Costs()
    capital: Capital
    benchmark: str | None = None

    @model_validator(mode="after")
    def validate_allocations(self) -> "AllocationRebalanceStrategy":
        symbols = set(self.universe.symbols)
        allocation_symbols = [allocation.symbol for allocation in self.target_allocations]
        if set(allocation_symbols) != symbols:
            raise ValueError("target_allocations must contain every universe symbol exactly once")
        if len(set(allocation_symbols)) != len(allocation_symbols):
            raise ValueError("target_allocations must not repeat symbols")
        if sum(allocation.weight for allocation in self.target_allocations) > 1 + 1e-9:
            raise ValueError("target allocation weights must sum to 1 or less")
        return self


StrategyDefinition = Union[Strategy, RegimeSwitchStrategy, AllocationRebalanceStrategy]


def validate_strategy_definition(payload: object) -> StrategyDefinition:
    """Keep V1 JSON compatible while routing explicit V2 requests safely."""

    if isinstance(payload, RegimeSwitchStrategy | AllocationRebalanceStrategy | Strategy):
        return payload
    if isinstance(payload, dict) and payload.get("strategy_type") == "REGIME_SWITCH":
        return RegimeSwitchStrategy.model_validate(payload)
    if isinstance(payload, dict) and payload.get("strategy_type") == "ALLOCATION_REBALANCE":
        return AllocationRebalanceStrategy.model_validate(payload)
    return Strategy.model_validate(payload)
