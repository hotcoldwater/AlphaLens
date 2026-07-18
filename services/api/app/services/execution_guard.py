import threading


class ExecutionGuard:
    """In-process guard preventing the same key (for example a draft_id) from
    running a backtest concurrently. AlphaLens runs as a single Render
    instance with a fully synchronous, in-process backtest engine, so an
    in-memory set is sufficient -- there is no multi-worker/queue setup that
    would need a distributed lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._in_flight: set[str] = set()

    def acquire(self, key: str) -> bool:
        with self._lock:
            if key in self._in_flight:
                return False
            self._in_flight.add(key)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            self._in_flight.discard(key)


backtest_execution_guard = ExecutionGuard()
