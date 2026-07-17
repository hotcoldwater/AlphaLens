from dataclasses import dataclass
from math import floor

import pandas as pd

from ..enums.strategy_types import RebalanceFrequency
from ..schemas.strategy_schema import AllocationRebalanceStrategy
from .engine import BacktestResult, Trade
from .metrics import annualized_volatility, sharpe_ratio


@dataclass
class Holding:
    quantity: int = 0
    entry_date: pd.Timestamp | None = None
    average_entry_price: float = 0.0
    entry_cost: float = 0.0


def _rebalance_period_key(index: pd.Timestamp, frequency: RebalanceFrequency) -> tuple[int, int]:
    """Return a (year, period) key that changes whenever a new rebalance window starts."""
    if frequency == RebalanceFrequency.WEEKLY:
        year, week, _ = index.isocalendar()
        return (int(year), int(week))
    if frequency == RebalanceFrequency.QUARTERLY:
        return (index.year, (index.month - 1) // 3)
    return (index.year, index.month)


def run_allocation_rebalance_backtest(
    data_by_symbol: dict[str, pd.DataFrame], strategy: AllocationRebalanceStrategy
) -> BacktestResult:
    """Run fixed target weights with first-common-session rebalancing at the configured frequency."""
    aligned = _align_data(data_by_symbol, strategy)
    weights = {item.symbol: item.weight for item in strategy.target_allocations}
    holdings = {symbol: Holding() for symbol in strategy.universe.symbols}
    cash = float(strategy.capital.initial_cash)
    initial_cash = cash
    total_cost = 0.0
    trades: list[Trade] = []
    equity_values: list[float] = []
    previous_period: tuple[int, int] | None = None

    for index in next(iter(aligned.values())).index:
        period = _rebalance_period_key(index, strategy.rebalance.frequency)
        if previous_period is None or period != previous_period:
            cash, rebalance_cost, completed = _rebalance(
                index, aligned, holdings, cash, weights, strategy
            )
            total_cost += rebalance_cost
            trades.extend(completed)
            previous_period = period
        equity_values.append(cash + sum(
            holding.quantity * float(aligned[symbol].loc[index, "close"])
            for symbol, holding in holdings.items()
        ))

    equity_curve = pd.Series(equity_values, index=next(iter(aligned.values())).index, name="equity")
    final_equity = float(equity_curve.iloc[-1])
    elapsed_days = max((equity_curve.index[-1] - equity_curve.index[0]).days, 1)
    trade_returns = [trade.return_rate for trade in trades]
    return BacktestResult(
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return=final_equity / initial_cash - 1,
        cagr=(final_equity / initial_cash) ** (365.25 / elapsed_days) - 1,
        max_drawdown=float((equity_curve / equity_curve.cummax() - 1).min()),
        volatility=annualized_volatility(equity_curve),
        sharpe_ratio=sharpe_ratio(equity_curve),
        win_rate=sum(value > 0 for value in trade_returns) / len(trades) if trades else 0.0,
        average_trade_return=sum(trade_returns) / len(trades) if trades else 0.0,
        average_holding_days=sum(trade.holding_days for trade in trades) / len(trades) if trades else 0.0,
        total_cost=total_cost,
        trade_count=len(trades),
        trades=trades,
        equity_curve=equity_curve,
    )


def _rebalance(
    index: pd.Timestamp,
    data: dict[str, pd.DataFrame],
    holdings: dict[str, Holding],
    cash: float,
    weights: dict[str, float],
    strategy: AllocationRebalanceStrategy,
) -> tuple[float, float, list[Trade]]:
    open_equity = cash + sum(
        holding.quantity * float(data[symbol].loc[index, "open"])
        for symbol, holding in holdings.items()
    )
    total_cost = 0.0
    completed: list[Trade] = []

    # Sell excess positions first, so every later purchase has settled cash available.
    for symbol, holding in holdings.items():
        raw_open = float(data[symbol].loc[index, "open"])
        target_value = open_equity * weights[symbol]
        current_value = holding.quantity * raw_open
        excess_quantity = max(holding.quantity - floor(target_value / raw_open), 0)
        if not excess_quantity:
            continue
        fill_price = raw_open * (1 - strategy.costs.slippage_rate)
        gross = excess_quantity * fill_price
        exit_cost = gross * (strategy.costs.commission_rate + strategy.costs.tax_rate)
        cash += gross - exit_cost
        total_cost += exit_cost
        assert holding.entry_date is not None
        allocated_entry_cost = holding.entry_cost * excess_quantity / holding.quantity
        invested = excess_quantity * holding.average_entry_price + allocated_entry_cost
        completed.append(Trade(
            entry_date=holding.entry_date,
            entry_price=holding.average_entry_price,
            exit_date=index,
            exit_price=fill_price,
            quantity=excess_quantity,
            entry_cost=allocated_entry_cost,
            exit_cost=exit_cost,
            pnl=gross - exit_cost - invested,
            return_rate=(gross - exit_cost - invested) / invested,
            holding_days=(index - holding.entry_date).days,
            symbol=symbol,
        ))
        holding.quantity -= excess_quantity
        holding.entry_cost -= allocated_entry_cost
        if holding.quantity == 0:
            holding.entry_date = None
            holding.average_entry_price = 0.0
            holding.entry_cost = 0.0

    for symbol, holding in holdings.items():
        raw_open = float(data[symbol].loc[index, "open"])
        target_value = open_equity * weights[symbol]
        current_value = holding.quantity * raw_open
        deficit_value = max(target_value - current_value, 0.0)
        fill_price = raw_open * (1 + strategy.costs.slippage_rate)
        unit_cost = fill_price * (1 + strategy.costs.commission_rate)
        quantity = min(floor(deficit_value / unit_cost), floor(cash / unit_cost))
        if not quantity:
            continue
        gross = quantity * fill_price
        entry_cost = gross * strategy.costs.commission_rate
        previous_quantity = holding.quantity
        cash -= gross + entry_cost
        total_cost += entry_cost
        holding.quantity += quantity
        holding.average_entry_price = (
            (holding.average_entry_price * previous_quantity + fill_price * quantity)
            / holding.quantity
        )
        holding.entry_cost += entry_cost
        if holding.entry_date is None:
            holding.entry_date = index
    return cash, total_cost, completed


def _align_data(
    data_by_symbol: dict[str, pd.DataFrame], strategy: AllocationRebalanceStrategy
) -> dict[str, pd.DataFrame]:
    normalized = {symbol.upper(): frame.copy() for symbol, frame in data_by_symbol.items()}
    common_index: pd.DatetimeIndex | None = None
    for symbol in strategy.universe.symbols:
        if symbol not in normalized:
            raise ValueError(f"missing market data for {symbol}")
        common_index = normalized[symbol].index if common_index is None else common_index.intersection(normalized[symbol].index)
    assert common_index is not None
    common_index = common_index.sort_values()
    if len(common_index) < 2:
        counts = ", ".join(f"{symbol}: {len(normalized[symbol])}개" for symbol in strategy.universe.symbols)
        raise ValueError(
            "ALLOCATION_REBALANCE requires at least two common trading dates "
            f"(found {len(common_index)}; supplied data points — {counts})"
        )
    return {symbol: normalized[symbol].loc[common_index] for symbol in strategy.universe.symbols}
