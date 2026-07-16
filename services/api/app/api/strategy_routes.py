from typing import Any

from fastapi import APIRouter
from pydantic import ValidationError

from ..schemas.strategy_schema import Strategy
from ..schemas.backtest_schema import StrategyValidationResponse
from ..schemas.strategy_parse_schema import StrategyLibraryResponse, StrategyVersionListResponse
from ..services.strategy_draft_store import strategy_draft_store

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


@router.get("", response_model=StrategyLibraryResponse)
def list_strategies() -> StrategyLibraryResponse:
    return strategy_draft_store.list_strategies()


@router.get("/{strategy_id}/versions", response_model=StrategyVersionListResponse)
def get_strategy_versions(strategy_id: str) -> StrategyVersionListResponse:
    return strategy_draft_store.versions(strategy_id)
