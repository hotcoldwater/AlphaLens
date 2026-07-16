from pydantic import BaseModel, ConfigDict, Field


class BacktestExplanation(BaseModel):
    """Interpretation of fixed backtest output; never a trading recommendation."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1_000)
    strengths: list[str] = Field(default_factory=list, max_length=4)
    risks: list[str] = Field(default_factory=list, max_length=4)
    observations: list[str] = Field(default_factory=list, max_length=4)
    disclaimer: str = Field(min_length=1, max_length=500)
