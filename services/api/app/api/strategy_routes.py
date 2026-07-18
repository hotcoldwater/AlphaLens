from typing import Any

from fastapi import APIRouter
from pydantic import ValidationError

from ..schemas.strategy_schema import validate_strategy_definition
from ..schemas.backtest_schema import (
    BacktestFailureResponse,
    StrategyBacktestListResponse,
    StrategyFailureListResponse,
    StrategyValidationResponse,
)
from ..services.backtest_failure_store import backtest_failure_store
from ..services.backtest_store import backtest_store
from ..schemas.strategy_parse_schema import (
    StrategyDraftResponse,
    StrategyLibraryResponse,
    StrategyVersionListResponse,
)
from ..services.strategy_draft_store import strategy_draft_store

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


@router.post("/validate", response_model=StrategyValidationResponse)
def validate_strategy(payload: dict[str, Any]) -> StrategyValidationResponse:
    try:
        validate_strategy_definition(payload)
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


@router.post("/{strategy_id}/versions/{version}/clone", response_model=StrategyDraftResponse)
def clone_strategy_version(strategy_id: str, version: int) -> StrategyDraftResponse:
    return strategy_draft_store.clone_version(strategy_id, version)


@router.get("/{strategy_id}/backtests", response_model=StrategyBacktestListResponse)
def get_strategy_backtests(strategy_id: str) -> StrategyBacktestListResponse:
    return backtest_store.list_for_strategy(strategy_id)


@router.get("/{strategy_id}/failures", response_model=StrategyFailureListResponse)
def get_strategy_failures(strategy_id: str) -> StrategyFailureListResponse:
    return StrategyFailureListResponse(
        strategy_id=strategy_id,
        failures=[
            BacktestFailureResponse(**row) for row in backtest_failure_store.list_for_strategy(strategy_id)
        ],
    )


@router.get("/{strategy_id}/versions", response_model=StrategyVersionListResponse)
def get_strategy_versions(strategy_id: str) -> StrategyVersionListResponse:
    return strategy_draft_store.versions(strategy_id)
