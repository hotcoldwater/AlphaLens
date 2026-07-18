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

    signal_symbols = request.strategy.signal_symbols()
    signal_data: dict[str, pd.DataFrame] | None = None
    if signal_symbols:
        assert request.data_by_symbol is not None
        signal_data = {}
        common_index = data.index
        for symbol in signal_symbols:
            bars = request.data_by_symbol[symbol.upper()]
            frame = pd.DataFrame([bar.model_dump() for bar in bars])
            frame["date"] = pd.to_datetime(frame["date"])
            frame = validate_ohlcv(frame.set_index("date"))
            frame = frame.loc[
                (frame.index.date >= request.strategy.period.start_date)
                & (frame.index.date <= request.strategy.period.end_date)
            ]
            signal_data[symbol] = frame
            common_index = common_index.intersection(frame.index)
        common_index = common_index.sort_values()
        if len(common_index) < 2:
            raise ValueError(
                "cross-asset condition requires at least two common trading dates "
                f"between {request.strategy.universe.symbols[0]} and {', '.join(sorted(signal_symbols))}"
            )
        data = data.loc[common_index]
        signal_data = {symbol: frame.loc[common_index] for symbol, frame in signal_data.items()}

    entry_signal, exit_signal = generate_strategy_signals(data, request.strategy, signal_data)
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
    _reject_incomplete_symbol_data(frames, request.strategy)
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


_MAX_DATA_GAP_DAYS = 10


def _reject_incomplete_symbol_data(
    frames: dict[str, pd.DataFrame], strategy: AllocationRebalanceStrategy
) -> None:
    """Reject execution when a symbol's data stops well before the requested period
    end (or starts well after its start) instead of silently shrinking the common
    trading-day intersection in _align_data. This usually indicates delisting, a
    trading halt, or an incomplete data pull rather than an ordinary holiday gap."""
    period_start = pd.Timestamp(strategy.period.start_date)
    period_end = pd.Timestamp(strategy.period.end_date)
    for symbol in strategy.universe.symbols:
        frame = frames[symbol]
        last_date = frame.index.max()
        first_date = frame.index.min()
        if (period_end - last_date).days > _MAX_DATA_GAP_DAYS:
            raise ValueError(
                f"{symbol} 데이터가 {last_date.date()}에 종료되어 요청 종료일 {strategy.period.end_date}보다 "
                f"{_MAX_DATA_GAP_DAYS}일 넘게 이릅니다. 상장폐지 또는 거래정지 가능성이 있어 실행을 거절합니다."
            )
        if (first_date - period_start).days > _MAX_DATA_GAP_DAYS:
            raise ValueError(
                f"{symbol} 데이터가 {first_date.date()}부터 시작되어 요청 시작일 {strategy.period.start_date}보다 "
                f"{_MAX_DATA_GAP_DAYS}일 넘게 늦습니다. 실행을 거절합니다."
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
