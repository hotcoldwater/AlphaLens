from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
