from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from ..enums import StrategyStatus
from ..schemas.strategy_parse_schema import (
    ConfirmedStrategyResponse,
    StrategyDraftResponse,
    StrategyParseResult,
)


class InMemoryStrategyDraftStore:
    """Temporary process-local draft/version store until the database phase."""

    def __init__(self) -> None:
        self._drafts: dict[str, StrategyDraftResponse] = {}
        self._lock = Lock()

    def create(self, raw_input: str, result: StrategyParseResult) -> StrategyDraftResponse:
        with self._lock:
            draft = StrategyDraftResponse(
                draft_id=str(uuid4()),
                status=StrategyStatus.READY_TO_CONFIRM,
                raw_input=raw_input,
                **result.model_dump(),
            )
            self._drafts[draft.draft_id] = draft
            return draft

    def get(self, draft_id: str) -> StrategyDraftResponse:
        with self._lock:
            draft = self._drafts.get(draft_id)
        if draft is None:
            raise HTTPException(status_code=404, detail="strategy draft not found")
        return draft

    def update(self, draft_id: str, strategy) -> StrategyDraftResponse:
        draft = self.get(draft_id)
        with self._lock:
            draft.strategy = strategy
            draft.status = StrategyStatus.READY_TO_CONFIRM
            draft.needs_confirmation = True
        return draft

    def confirm(self, draft_id: str) -> ConfirmedStrategyResponse:
        draft = self.get(draft_id)
        if draft.status != StrategyStatus.READY_TO_CONFIRM:
            raise HTTPException(status_code=409, detail="strategy draft is not awaiting confirmation")
        with self._lock:
            strategy_id = str(uuid4())
            draft.status = StrategyStatus.CONFIRMED
            draft.needs_confirmation = False
        return ConfirmedStrategyResponse(
            strategy_id=strategy_id,
            version=1,
            status=StrategyStatus.CONFIRMED,
            strategy=draft.strategy,
        )


strategy_draft_store = InMemoryStrategyDraftStore()
