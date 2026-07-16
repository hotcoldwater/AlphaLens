from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .strategy_schema import Strategy


class StrategyParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    raw_input: Annotated[str, Field(min_length=1, max_length=10_000)]


class StrategyParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy: Strategy
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_confirmation: bool = True
