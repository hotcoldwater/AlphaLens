import json
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from ..core.database import connect, initialize_schema
from ..schemas.backtest_schema import BacktestResponse


class BacktestStore:
    """SQLite-backed backtest result store."""

    def __init__(self) -> None:
        initialize_schema()
        self._lock = Lock()

    def save(self, response: BacktestResponse) -> BacktestResponse:
        backtest_id = str(uuid4())
        saved = response.model_copy(update={"backtest_id": backtest_id})
        with self._lock, connect() as connection:
            connection.execute(
                "INSERT INTO backtest_runs (backtest_id, status, data_version, result_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    backtest_id,
                    saved.status.value,
                    saved.data_version,
                    json.dumps(saved.model_dump(mode="json")),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return saved

    def get(self, backtest_id: str) -> BacktestResponse:
        with connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM backtest_runs WHERE backtest_id = ?", (backtest_id,)
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="backtest not found")
        return BacktestResponse.model_validate(json.loads(row["result_json"]))


backtest_store = BacktestStore()
