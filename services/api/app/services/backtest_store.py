from threading import Lock
from uuid import uuid4

from fastapi import HTTPException

from ..schemas.backtest_schema import BacktestResponse


class InMemoryBacktestStore:
    """Temporary process-local store until the database layer is introduced."""

    def __init__(self) -> None:
        self._runs: dict[str, BacktestResponse] = {}
        self._lock = Lock()

    def save(self, response: BacktestResponse) -> BacktestResponse:
        with self._lock:
            backtest_id = str(uuid4())
            saved = response.model_copy(update={"backtest_id": backtest_id})
            self._runs[backtest_id] = saved
        return saved

    def get(self, backtest_id: str) -> BacktestResponse:
        with self._lock:
            response = self._runs.get(backtest_id)
        if response is None:
            raise HTTPException(status_code=404, detail="backtest not found")
        return response


backtest_store = InMemoryBacktestStore()
