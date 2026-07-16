from fastapi import APIRouter, HTTPException

from ..clients.openai_client import OpenAIClientError
from ..schemas.backtest_schema import BacktestRequest, BacktestResponse
from ..schemas.strategy_parse_schema import (
    ConfirmedStrategyResponse,
    DraftBacktestRequest,
    StrategyDraftResponse,
    StrategyDraftUpdate,
    StrategyParseRequest,
)
from ..services.strategy_parser_service import StrategyParserService
from ..services.strategy_draft_store import strategy_draft_store
from .backtest_routes import _to_response

router = APIRouter(prefix="/api/v1/strategy-drafts", tags=["strategy-drafts"])
parser_service = StrategyParserService()


@router.post("/parse", response_model=StrategyDraftResponse)
def parse_strategy(request: StrategyParseRequest) -> StrategyDraftResponse:
    try:
        result = parser_service.parse(request.raw_input)
        return strategy_draft_store.create(request.raw_input, result)
    except OpenAIClientError as error:
        status_code = 503 if "not configured" in str(error) else 502
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.get("/{draft_id}", response_model=StrategyDraftResponse)
def get_strategy_draft(draft_id: str) -> StrategyDraftResponse:
    return strategy_draft_store.get(draft_id)


@router.patch("/{draft_id}", response_model=StrategyDraftResponse)
def update_strategy_draft(
    draft_id: str, update: StrategyDraftUpdate
) -> StrategyDraftResponse:
    return strategy_draft_store.update(draft_id, update.strategy)


@router.post("/{draft_id}/confirm", response_model=ConfirmedStrategyResponse)
def confirm_strategy_draft(draft_id: str) -> ConfirmedStrategyResponse:
    return strategy_draft_store.confirm(draft_id)


@router.post("/{draft_id}/backtest", response_model=BacktestResponse)
def backtest_confirmed_draft(
    draft_id: str, request: DraftBacktestRequest
) -> BacktestResponse:
    draft = strategy_draft_store.get(draft_id)
    if draft.status.value != "CONFIRMED":
        raise HTTPException(status_code=409, detail="strategy must be confirmed before backtest")
    return _to_response(BacktestRequest(strategy=draft.strategy, data=request.data))
