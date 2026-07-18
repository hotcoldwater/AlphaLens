from datetime import date, datetime
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .strategy_schema import AllocationRebalanceStrategy, RegimeSwitchStrategy, Strategy, StrategyDefinition
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
    provider: Literal["YFINANCE", "PYKRX", "FMP"]
    symbol: str = Field(min_length=1, max_length=32)
    start_date: date
    end_date: date
    adjusted_price: bool = True

    @model_validator(mode="after")
    def validate_provider_symbol(self) -> "MarketDataFetchRequest":
        symbol = self.symbol.strip()
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        if self.provider == "PYKRX" and not re.fullmatch(r"\d{6}", symbol):
            raise ValueError("PYKRX symbol must be a six-digit KRX ticker, for example 005930")
        if self.provider in {"YFINANCE", "FMP"} and not re.fullmatch(r"[A-Za-z0-9.^=_-]+", symbol):
            raise ValueError("US market symbol contains unsupported characters")
        self.symbol = symbol
        return self


class MarketDataFetchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    symbol: str
    adjustment: str
    data_version: str
    data_start_date: date
    data_end_date: date
    data_points: int
    collected_at: datetime
    data: list[OHLCVBar]


class MarketDataSource(BaseModel):
    """Provider metadata retained with a backtest for reproducibility."""

    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=32)
    provider: str = Field(min_length=1, max_length=32)
    adjustment: str = Field(min_length=1, max_length=160)
    data_version: str = Field(min_length=1, max_length=80)
    collected_at: datetime


class MarketSymbolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    symbol: str
    name: str


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: StrategyDefinition
    data: list[OHLCVBar] | None = None
    data_by_symbol: dict[str, Annotated[list[OHLCVBar], Field(min_length=1)]] | None = None
    data_sources: list[MarketDataSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_data_shape(self) -> "BacktestRequest":
        if isinstance(self.strategy, RegimeSwitchStrategy | AllocationRebalanceStrategy):
            if not self.data_by_symbol:
                raise ValueError("multi-asset strategy requires data_by_symbol")
            expected = set(self.strategy.universe.symbols)
            actual = {symbol.upper() for symbol in self.data_by_symbol}
            if actual != expected:
                raise ValueError("data_by_symbol must contain exactly the strategy universe symbols")
            return self
        if not self.data:
            raise ValueError("single-stock strategy requires data")
        signal_symbols = self.strategy.signal_symbols()
        if signal_symbols:
            provided = {symbol.upper() for symbol in (self.data_by_symbol or {})}
            missing = signal_symbols - provided
            if missing:
                raise ValueError(f"missing signal data for {', '.join(sorted(missing))}")
        elif self.data_by_symbol is not None:
            raise ValueError("single-stock strategy does not accept data_by_symbol")
        return self


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
    symbol: str | None = None


class EquityPoint(BaseModel):
    date: date
    equity: float


class SymbolAttributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    symbol: str
    trade_count: int
    total_pnl: float
    contribution_to_return: float
    average_holding_days: float


class BacktestResponse(BaseModel):
    backtest_id: str
    status: BacktestStatus
    strategy_id: str | None = None
    strategy_version: int | None = None
    currency: str = "KRW"
    data_version: str = "unversioned"
    data_start_date: date | None = None
    data_end_date: date | None = None
    data_points: int = 0
    data_sources: list[MarketDataSource] = Field(default_factory=list)
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
    symbol_attribution: list[SymbolAttributionResponse] = Field(default_factory=list)


class BacktestRunSummary(BaseModel):
    backtest_id: str
    status: BacktestStatus
    strategy_version: int | None = None
    currency: str = "KRW"
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
