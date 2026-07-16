from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .strategy_schema import Strategy
from ..enums import BacktestStatus


class OHLCVBar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Strategy
    data: Annotated[list[OHLCVBar], Field(min_length=1)]


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entry_date: date
    entry_price: float
    exit_date: date
    exit_price: float
    quantity: int
    entry_cost: float
    exit_cost: float
    pnl: float
    return_rate: float
    holding_days: int


class EquityPoint(BaseModel):
    date: date
    equity: float


class BacktestResponse(BaseModel):
    backtest_id: str
    status: BacktestStatus
    data_version: str = "unversioned"
    data_start_date: date | None = None
    data_end_date: date | None = None
    data_points: int = 0
    initial_cash: float
    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    win_rate: float
    average_trade_return: float
    average_holding_days: float
    total_cost: float
    trade_count: int
    trades: list[TradeResponse]
    equity_curve: list[EquityPoint]


class StrategyValidationResponse(BaseModel):
    valid: bool
    errors: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
