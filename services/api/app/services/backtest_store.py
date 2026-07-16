import json
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from ..core.database import connect, initialize_schema
from ..schemas.backtest_schema import BacktestResponse, BacktestRunSummary, StrategyBacktestListResponse


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
                "INSERT INTO backtest_runs (backtest_id, status, data_version, strategy_id, strategy_version, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    backtest_id,
                    saved.status.value,
                    saved.data_version,
                    saved.strategy_id,
                    saved.strategy_version,
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

    def list_for_strategy(self, strategy_id: str) -> StrategyBacktestListResponse:
        with connect() as connection:
            rows = connection.execute(
                "SELECT * FROM backtest_runs WHERE strategy_id = ? ORDER BY created_at DESC",
                (strategy_id,),
            ).fetchall()
        return StrategyBacktestListResponse(
            strategy_id=strategy_id,
            runs=[
                BacktestRunSummary(
                    backtest_id=row["backtest_id"],
                    status=row["status"],
                    strategy_version=row["strategy_version"],
                    created_at=row["created_at"],
                    data_version=row["data_version"],
                    **{
                        field: json.loads(row["result_json"])[field]
                        for field in (
                            "data_start_date", "data_end_date", "data_points", "total_return",
                            "max_drawdown", "sharpe_ratio", "final_equity", "trade_count",
                        )
                    },
                )
                for row in rows
            ],
        )


backtest_store = BacktestStore()
