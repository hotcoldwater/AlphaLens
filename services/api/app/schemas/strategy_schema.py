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
