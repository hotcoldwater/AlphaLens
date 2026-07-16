from typing import Any

from fastapi import APIRouter
from pydantic import ValidationError

from ..schemas.strategy_schema import Strategy
from ..schemas.backtest_schema import StrategyValidationResponse

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.post("/validate", response_model=StrategyValidationResponse)
def validate_strategy(payload: dict[str, Any]) -> StrategyValidationResponse:
    try:
        Strategy.model_validate(payload)
    except ValidationError as error:
        errors = [
            {"type": item["type"], "loc": list(item["loc"]), "msg": item["msg"]}
            for item in error.errors()
        ]
        return StrategyValidationResponse(valid=False, errors=errors)
    return StrategyValidationResponse(valid=True)
