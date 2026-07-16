import json
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from ..core.database import connect, execute, initialize_schema
from ..enums import StrategyStatus
from ..schemas.strategy_parse_schema import (
    ConfirmedStrategyResponse,
    StrategyDraftResponse,
    StrategyParseResult,
    StrategyLibraryItem,
    StrategyLibraryResponse,
    StrategyVersionListResponse,
    StrategyVersionResponse,
)
from ..schemas.strategy_schema import StrategyDefinition, validate_strategy_definition


class StrategyDraftStore:
    """Durable draft and strategy-version store for SQLite or PostgreSQL."""

    def __init__(self) -> None:
        initialize_schema()
        self._lock = Lock()

    def create(self, raw_input: str, result: StrategyParseResult) -> StrategyDraftResponse:
        draft_id = str(uuid4())
        draft = StrategyDraftResponse(
            draft_id=draft_id,
            status=(StrategyStatus.NEEDS_INPUT if result.needs_clarification else StrategyStatus.READY_TO_CONFIRM),
            raw_input=raw_input,
            **result.model_dump(),
        )
        with self._lock, connect() as connection:
            execute(
                connection,
                """
                INSERT INTO strategy_drafts
                (draft_id, raw_input, strategy_json, status, missing_fields_json,
                 assumptions_json, warnings_json, needs_confirmation, needs_clarification)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    int(draft.needs_clarification),
                ),
            )
        return draft

    def get(self, draft_id: str) -> StrategyDraftResponse:
        with connect() as connection:
            row = execute(
                connection,
                "SELECT * FROM strategy_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="strategy draft not found")
        return _draft_from_row(row)

    def update(self, draft_id: str, strategy: StrategyDefinition) -> StrategyDraftResponse:
        draft = self.get(draft_id)
        with self._lock, connect() as connection:
            execute(
                connection,
                "UPDATE strategy_drafts SET strategy_json = ?, status = ?, needs_confirmation = 1, needs_clarification = 0 WHERE draft_id = ?",
                (json.dumps(strategy.model_dump(mode="json")), StrategyStatus.READY_TO_CONFIRM.value, draft_id),
            )
        return self.get(draft_id)

    def confirm(self, draft_id: str) -> ConfirmedStrategyResponse:
        draft = self.get(draft_id)
        if draft.status != StrategyStatus.READY_TO_CONFIRM:
            raise HTTPException(status_code=409, detail="strategy draft is not awaiting confirmation")
        with self._lock, connect() as connection:
            strategy_id = draft.strategy_id or str(uuid4())
            version = execute(
                connection,
                "SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM strategy_versions WHERE strategy_id = ?",
                (strategy_id,),
            ).fetchone()["next_version"]
            execute(
                connection,
                "UPDATE strategy_drafts SET status = ?, needs_confirmation = 0, strategy_id = ?, strategy_version = ? WHERE draft_id = ?",
                (StrategyStatus.CONFIRMED.value, strategy_id, version, draft_id),
            )
            execute(
                connection,
                """
                INSERT INTO strategy_versions
                (strategy_id, version, draft_id, strategy_json, confirmed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    strategy_id,
                    version,
                    draft_id,
                    json.dumps(draft.strategy.model_dump(mode="json")),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return ConfirmedStrategyResponse(
            strategy_id=strategy_id,
            version=version,
            status=StrategyStatus.CONFIRMED,
            strategy=draft.strategy,
        )

    def versions(self, strategy_id: str) -> StrategyVersionListResponse:
        with connect() as connection:
            rows = execute(
                connection,
                "SELECT * FROM strategy_versions WHERE strategy_id = ? ORDER BY version",
                (strategy_id,),
            ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="strategy not found")
        return StrategyVersionListResponse(
            strategy_id=strategy_id,
            versions=[
                StrategyVersionResponse(
                    strategy_id=row["strategy_id"],
                    version=row["version"],
                    draft_id=row["draft_id"],
                    confirmed_at=row["confirmed_at"],
                    strategy=validate_strategy_definition(json.loads(row["strategy_json"])),
                )
                for row in rows
            ],
        )

    def list_strategies(self) -> StrategyLibraryResponse:
        """Return one card per strategy, using its latest confirmed version."""
        with connect() as connection:
            rows = execute(
                connection,
                """
                SELECT versions.* FROM strategy_versions AS versions
                INNER JOIN (
                    SELECT strategy_id, MAX(version) AS latest_version
                    FROM strategy_versions
                    GROUP BY strategy_id
                ) AS latest
                ON versions.strategy_id = latest.strategy_id
                AND versions.version = latest.latest_version
                ORDER BY versions.confirmed_at DESC
                """
            ).fetchall()
        return StrategyLibraryResponse(
            strategies=[
                StrategyLibraryItem(
                    strategy_id=row["strategy_id"],
                    latest_version=row["version"],
                    confirmed_at=row["confirmed_at"],
                    strategy=validate_strategy_definition(json.loads(row["strategy_json"])),
                )
                for row in rows
            ]
        )

    def clone_version(self, strategy_id: str, version: int) -> StrategyDraftResponse:
        """Create a new unconfirmed draft from an immutable confirmed version."""
        with connect() as connection:
            row = execute(
                connection,
                "SELECT * FROM strategy_versions WHERE strategy_id = ? AND version = ?",
                (strategy_id, version),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="strategy version not found")
        strategy = validate_strategy_definition(json.loads(row["strategy_json"]))
        result = StrategyParseResult(
            strategy=strategy,
            assumptions=[f"{strategy_id}의 확정 버전 {version}을 새 초안으로 복제했습니다."],
            warnings=["복제본은 원본 전략의 다음 버전으로 저장됩니다. 실행 전에 조건과 비용을 다시 확인하세요."],
            needs_confirmation=True,
        )
        cloned = self.create(f"Cloned strategy {strategy_id} version {version}", result)
        with self._lock, connect() as connection:
            execute(
                connection,
                "UPDATE strategy_drafts SET strategy_id = ? WHERE draft_id = ?",
                (strategy_id, cloned.draft_id),
            )
        return self.get(cloned.draft_id)


def _draft_from_row(row: object) -> StrategyDraftResponse:
    return StrategyDraftResponse(
        draft_id=row["draft_id"],
        raw_input=row["raw_input"],
        strategy=validate_strategy_definition(json.loads(row["strategy_json"])),
        status=StrategyStatus(row["status"]),
        strategy_id=row["strategy_id"],
        strategy_version=row["strategy_version"],
        missing_fields=json.loads(row["missing_fields_json"]),
        assumptions=json.loads(row["assumptions_json"]),
        warnings=json.loads(row["warnings_json"]),
        needs_confirmation=bool(row["needs_confirmation"]),
        needs_clarification=bool(row["needs_clarification"]),
    )


strategy_draft_store = StrategyDraftStore()
