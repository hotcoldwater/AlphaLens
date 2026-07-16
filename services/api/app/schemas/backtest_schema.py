from datetime import date
from typing import Annotated, Literal

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


class MarketDataFetchRequest(BaseModel):
    """Request daily market data from a configured external provider."""

    model_config = ConfigDict(extra="forbid")
    provider: Literal["FMP", "KRX"]
    symbol: str = Field(min_length=1, max_length=32)
    start_date: date
    end_date: date
    adjusted_price: bool = True


class MarketDataFetchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    symbol: str
    adjustment: str
    data_version: str
    data_start_date: date
    data_end_date: date
    data_points: int
    data: list[OHLCVBar]


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
    strategy_id: str | None = None
    strategy_version: int | None = None
    data_version: str = "unversioned"
    data_start_date: date | None = None
    data_end_date: date | None = None
    data_points: int = 0
    benchmark_name: str = "Same-data Buy & Hold"
    benchmark_total_return: float = 0.0
    benchmark_max_drawdown: float = 0.0
    benchmark_equity_curve: list[EquityPoint] = Field(default_factory=list)
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


class BacktestRunSummary(BaseModel):
    backtest_id: str
    status: BacktestStatus
    strategy_version: int | None = None
    created_at: str
    data_version: str
    data_start_date: date | None = None
    data_end_date: date | None = None
    data_points: int = 0
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    final_equity: float
    trade_count: int


class StrategyBacktestListResponse(BaseModel):
    strategy_id: str
    runs: list[BacktestRunSummary]


class StrategyValidationResponse(BaseModel):
    valid: bool
    errors: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
