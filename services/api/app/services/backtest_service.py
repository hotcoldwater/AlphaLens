import pandas as pd

from ..backtest_engine.engine import BacktestResult, run_backtest
from ..backtest_engine.market_data import validate_ohlcv
from ..backtest_engine.signal_generator import generate_strategy_signals
from ..schemas.backtest_schema import BacktestRequest


def execute_backtest(request: BacktestRequest) -> BacktestResult:
    data = pd.DataFrame([bar.model_dump() for bar in request.data])
    data["date"] = pd.to_datetime(data["date"])
    data = data.set_index("date")
    data = validate_ohlcv(data)
    data = data.loc[
        (data.index.date >= request.strategy.period.start_date)
        & (data.index.date <= request.strategy.period.end_date)
    ]
    if data.empty:
        raise ValueError("no market data exists within strategy period")
    entry_signal, exit_signal = generate_strategy_signals(data, request.strategy)
    return run_backtest(data, entry_signal, exit_signal, request.strategy)
