import json
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from ..core.database import connect, initialize_schema
from ..enums import StrategyStatus
from ..schemas.strategy_parse_schema import (
    ConfirmedStrategyResponse,
    StrategyDraftResponse,
    StrategyParseResult,
)
from ..schemas.strategy_schema import Strategy


class StrategyDraftStore:
    """SQLite-backed draft and strategy-version store."""

    def __init__(self) -> None:
        initialize_schema()
        self._lock = Lock()

    def create(self, raw_input: str, result: StrategyParseResult) -> StrategyDraftResponse:
        draft_id = str(uuid4())
        draft = StrategyDraftResponse(
            draft_id=draft_id,
            status=StrategyStatus.READY_TO_CONFIRM,
            raw_input=raw_input,
            **result.model_dump(),
        )
        with self._lock, connect() as connection:
            connection.execute(
                """
                INSERT INTO strategy_drafts
                (draft_id, raw_input, strategy_json, status, missing_fields_json,
                 assumptions_json, warnings_json, needs_confirmation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.draft_id,
                    draft.raw_input,
                    json.dumps(draft.strategy.model_dump(mode="json")),
                    draft.status.value,
                    json.dumps(draft.missing_fields),
                    json.dumps(draft.assumptions),
                    json.dumps(draft.warnings),
                    int(draft.needs_confirmation),
                ),
            )
        return draft

    def get(self, draft_id: str) -> StrategyDraftResponse:
        with connect() as connection:
            row = connection.execute(
                "SELECT * FROM strategy_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="strategy draft not found")
        return _draft_from_row(row)

    def update(self, draft_id: str, strategy: Strategy) -> StrategyDraftResponse:
        draft = self.get(draft_id)
        with self._lock, connect() as connection:
            connection.execute(
                "UPDATE strategy_drafts SET strategy_json = ?, status = ?, needs_confirmation = 1 WHERE draft_id = ?",
                (json.dumps(strategy.model_dump(mode="json")), StrategyStatus.READY_TO_CONFIRM.value, draft_id),
            )
        return self.get(draft_id)

    def confirm(self, draft_id: str) -> ConfirmedStrategyResponse:
        draft = self.get(draft_id)
        if draft.status != StrategyStatus.READY_TO_CONFIRM:
            raise HTTPException(status_code=409, detail="strategy draft is not awaiting confirmation")
        strategy_id = str(uuid4())
        with self._lock, connect() as connection:
            connection.execute(
                "UPDATE strategy_drafts SET status = ?, needs_confirmation = 0 WHERE draft_id = ?",
                (StrategyStatus.CONFIRMED.value, draft_id),
            )
            connection.execute(
                """
                INSERT INTO strategy_versions
                (strategy_id, version, draft_id, strategy_json, confirmed_at)
                VALUES (?, 1, ?, ?, ?)
                """,
                (
                    strategy_id,
                    draft_id,
                    json.dumps(draft.strategy.model_dump(mode="json")),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return ConfirmedStrategyResponse(
            strategy_id=strategy_id,
            version=1,
            status=StrategyStatus.CONFIRMED,
            strategy=draft.strategy,
        )


def _draft_from_row(row: object) -> StrategyDraftResponse:
    return StrategyDraftResponse(
        draft_id=row["draft_id"],
        raw_input=row["raw_input"],
        strategy=Strategy.model_validate(json.loads(row["strategy_json"])),
        status=StrategyStatus(row["status"]),
        missing_fields=json.loads(row["missing_fields_json"]),
        assumptions=json.loads(row["assumptions_json"]),
        warnings=json.loads(row["warnings_json"]),
        needs_confirmation=bool(row["needs_confirmation"]),
    )


strategy_draft_store = StrategyDraftStore()
