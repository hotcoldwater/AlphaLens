from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from ..core.database import connect, execute, initialize_schema


class BacktestFailureStore:
    """Records a trace of failed backtest executions -- previously a failed
    run returned an error to the caller but left no record anywhere."""

    def __init__(self) -> None:
        initialize_schema()
        self._lock = Lock()

    def record(
        self,
        error_message: str,
        draft_id: str | None = None,
        strategy_id: str | None = None,
        strategy_version: int | None = None,
    ) -> None:
        with self._lock, connect() as connection:
            execute(
                connection,
                """
                INSERT INTO backtest_failures
                (id, draft_id, strategy_id, strategy_version, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    draft_id,
                    strategy_id,
                    strategy_version,
                    error_message,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_for_strategy(self, strategy_id: str, limit: int = 20) -> list[dict]:
        with connect() as connection:
            rows = execute(
                connection,
                """
                SELECT id, draft_id, strategy_id, strategy_version, error_message, created_at
                FROM backtest_failures WHERE strategy_id = ? ORDER BY created_at DESC LIMIT ?
                """,
                (strategy_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]


backtest_failure_store = BacktestFailureStore()
