from dataclasses import dataclass

import pandas as pd

from ..backtest_engine.engine import BacktestResult, run_backtest
from ..backtest_engine.market_data import DataVersion, build_data_version, build_multi_asset_data_version, validate_ohlcv
from ..backtest_engine.metrics import buy_and_hold_equity_curve, maximum_drawdown
from ..backtest_engine.regime_switch import run_regime_switch_backtest
from ..backtest_engine.allocation_rebalance import run_allocation_rebalance_backtest
from ..backtest_engine.signal_generator import generate_strategy_signals
from ..schemas.backtest_schema import BacktestRequest
from ..schemas.strategy_schema import AllocationRebalanceStrategy, RegimeSwitchStrategy


@dataclass(frozen=True)
class BacktestExecution:
    result: BacktestResult
    data_version: DataVersion
    benchmark_equity_curve: pd.Series
    benchmark_total_return: float
    benchmark_max_drawdown: float


def execute_backtest(request: BacktestRequest) -> BacktestExecution:
    if isinstance(request.strategy, RegimeSwitchStrategy):
        return _execute_regime_switch_backtest(request)
    if isinstance(request.strategy, AllocationRebalanceStrategy):
        return _execute_allocation_rebalance_backtest(request)
    assert request.data is not None
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
    benchmark_curve = buy_and_hold_equity_curve(data["close"], float(request.strategy.capital.initial_cash))
    return BacktestExecution(
        result=run_backtest(data, entry_signal, exit_signal, request.strategy),
        data_version=build_data_version(data),
        benchmark_equity_curve=benchmark_curve,
        benchmark_total_return=float(benchmark_curve.iloc[-1] / benchmark_curve.iloc[0] - 1),
        benchmark_max_drawdown=maximum_drawdown(benchmark_curve),
    )


def _execute_regime_switch_backtest(request: BacktestRequest) -> BacktestExecution:
    assert isinstance(request.strategy, RegimeSwitchStrategy)
    assert request.data_by_symbol is not None
    frames: dict[str, pd.DataFrame] = {}
    for raw_symbol, bars in request.data_by_symbol.items():
        data = pd.DataFrame([bar.model_dump() for bar in bars])
        data["date"] = pd.to_datetime(data["date"])
        data = validate_ohlcv(data.set_index("date"))
        data = data.loc[
            (data.index.date >= request.strategy.period.start_date)
            & (data.index.date <= request.strategy.period.end_date)
        ]
        if data.empty:
            raise ValueError(f"no market data exists within strategy period for {raw_symbol.upper()}")
        frames[raw_symbol.upper()] = data
    result = run_regime_switch_backtest(frames, request.strategy)
    version = build_multi_asset_data_version(frames)
    benchmark_data = frames[request.strategy.default_symbol]
    benchmark_curve = buy_and_hold_equity_curve(
        benchmark_data["close"], float(request.strategy.capital.initial_cash)
    )
    return BacktestExecution(
        result=result,
        data_version=version,
        benchmark_equity_curve=benchmark_curve,
        benchmark_total_return=float(benchmark_curve.iloc[-1] / benchmark_curve.iloc[0] - 1),
        benchmark_max_drawdown=maximum_drawdown(benchmark_curve),
    )


def _execute_allocation_rebalance_backtest(request: BacktestRequest) -> BacktestExecution:
    assert isinstance(request.strategy, AllocationRebalanceStrategy)
    frames = _build_multi_asset_frames(request)
    result = run_allocation_rebalance_backtest(frames, request.strategy)
    version = build_multi_asset_data_version(frames)
    benchmark_symbol = request.strategy.target_allocations[0].symbol
    benchmark_curve = buy_and_hold_equity_curve(
        frames[benchmark_symbol]["close"], float(request.strategy.capital.initial_cash)
    )
    return BacktestExecution(
        result=result,
        data_version=version,
        benchmark_equity_curve=benchmark_curve,
        benchmark_total_return=float(benchmark_curve.iloc[-1] / benchmark_curve.iloc[0] - 1),
        benchmark_max_drawdown=maximum_drawdown(benchmark_curve),
    )


def _build_multi_asset_frames(request: BacktestRequest) -> dict[str, pd.DataFrame]:
    assert request.data_by_symbol is not None
    frames: dict[str, pd.DataFrame] = {}
    for raw_symbol, bars in request.data_by_symbol.items():
        data = pd.DataFrame([bar.model_dump() for bar in bars])
        data["date"] = pd.to_datetime(data["date"])
        data = validate_ohlcv(data.set_index("date"))
        data = data.loc[
            (data.index.date >= request.strategy.period.start_date)
            & (data.index.date <= request.strategy.period.end_date)
        ]
        if data.empty:
            raise ValueError(f"no market data exists within strategy period for {raw_symbol.upper()}")
        frames[raw_symbol.upper()] = data
    return frames
