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
from ..services.strategy_parser_service import (
    StrategyParserService,
    requires_external_signal_support,
)
from ..services.backtest_failure_store import backtest_failure_store
from ..services.execution_guard import backtest_execution_guard
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
    if requires_external_signal_support(draft.raw_input, draft.strategy):
        raise HTTPException(
            status_code=409,
            detail=(
                "요청에 KOSPI·KOSDAQ 등 별도 지수를 신호로 쓰려는 의도가 있지만, 신호 종목이 "
                "주문 종목과 분리되어 해석되지 않았습니다. 조건을 수정한 뒤 다시 확정하세요."
            ),
        )
    if draft.status.value != "CONFIRMED":
        raise HTTPException(status_code=409, detail="strategy must be confirmed before backtest")
    if not backtest_execution_guard.acquire(draft_id):
        raise HTTPException(
            status_code=409,
            detail="이 초안에 대한 백테스트가 이미 실행 중입니다. 완료된 뒤 다시 시도하세요.",
        )
    try:
        return _to_response(
            BacktestRequest(
                strategy=draft.strategy,
                data=request.data,
                data_by_symbol=request.data_by_symbol,
                data_sources=request.data_sources,
            ),
            strategy_id=draft.strategy_id,
            strategy_version=draft.strategy_version,
        )
    except HTTPException as error:
        backtest_failure_store.record(
            error_message=str(error.detail),
            draft_id=draft_id,
            strategy_id=draft.strategy_id,
            strategy_version=draft.strategy_version,
        )
        raise
    except Exception as error:
        backtest_failure_store.record(
            error_message=str(error),
            draft_id=draft_id,
            strategy_id=draft.strategy_id,
            strategy_version=draft.strategy_version,
        )
        raise
    finally:
        backtest_execution_guard.release(draft_id)
