from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .strategy_schema import StrategyDefinition
from ..enums import StrategyStatus


class StrategyParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_input: Annotated[str, Field(min_length=1, max_length=10_000)]


class StrategyParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: StrategyDefinition
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True
    needs_clarification: bool = False


class StrategyDraftResponse(StrategyParseResult):
    draft_id: str
    status: StrategyStatus
    raw_input: str
    strategy_id: str | None = None
    strategy_version: int | None = None


class StrategyDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: StrategyDefinition


class ConfirmedStrategyResponse(BaseModel):
    strategy_id: str
    version: int
    status: StrategyStatus
    strategy: StrategyDefinition


class StrategyVersionResponse(BaseModel):
    strategy_id: str
    version: int
    draft_id: str
    confirmed_at: str
    strategy: StrategyDefinition


class StrategyVersionListResponse(BaseModel):
    strategy_id: str
    versions: list[StrategyVersionResponse]


class StrategyLibraryItem(BaseModel):
    strategy_id: str
    latest_version: int
    confirmed_at: str
    strategy: StrategyDefinition


class StrategyLibraryResponse(BaseModel):
    strategies: list[StrategyLibraryItem]


class DraftBacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: list["OHLCVBar"] | None = None
    data_by_symbol: dict[str, Annotated[list["OHLCVBar"], Field(min_length=1)]] | None = None


from .backtest_schema import OHLCVBar
