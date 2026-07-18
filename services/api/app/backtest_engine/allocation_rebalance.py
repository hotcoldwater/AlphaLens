from dataclasses import dataclass
from math import floor

import pandas as pd

from ..enums.strategy_types import RebalanceFrequency
from ..schemas.strategy_schema import AllocationRebalanceStrategy
from .engine import BacktestResult, Trade, compute_symbol_attribution
from .metrics import annualized_volatility, sharpe_ratio
from .signal_generator import evaluate_condition


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


def _resolve_conditional_weights(
    aligned: dict[str, pd.DataFrame], strategy: AllocationRebalanceStrategy
) -> list[tuple[pd.Series, dict[str, float]]]:
    """Pre-evaluate each conditional rule's condition once over the full aligned
    index. Operands may reference any universe symbol via IndicatorReference.symbol;
    an operand with no symbol defaults to the first universe symbol."""
    if not strategy.conditional_target_allocations:
        return []
    primary = aligned[strategy.universe.symbols[0]]
    return [
        (
            evaluate_condition(primary, rule.condition, aligned),
            {item.symbol: item.weight for item in rule.target_allocations},
        )
        for rule in strategy.conditional_target_allocations
    ]


def _active_weights(
    index: pd.Timestamp,
    conditional_weights: list[tuple[pd.Series, dict[str, float]]],
    base_weights: dict[str, float],
) -> dict[str, float]:
    """First matching conditional rule wins; otherwise fall back to the base weights."""
    for series, weights in conditional_weights:
        if bool(series.loc[index]):
            return weights
    return base_weights


def run_allocation_rebalance_backtest(
    data_by_symbol: dict[str, pd.DataFrame], strategy: AllocationRebalanceStrategy
) -> BacktestResult:
    """Run target weights with first-common-session rebalancing at the configured frequency."""
    aligned = _align_data(data_by_symbol, strategy)
    base_weights = {item.symbol: item.weight for item in strategy.target_allocations}
    conditional_weights = _resolve_conditional_weights(aligned, strategy)
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
            weights = _active_weights(index, conditional_weights, base_weights)
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
        symbol_attribution=compute_symbol_attribution(trades, initial_cash),
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
    tolerance = strategy.rebalance.weight_tolerance
    lot = strategy.rebalance.min_order_lot

    def within_tolerance(symbol: str, raw_open: float, quantity: int) -> bool:
        # A zero holding has no "current weight" to tolerate a deviation from --
        # tolerance only ever suppresses trimming/topping-up an existing position,
        # never the initial purchase that establishes it.
        if quantity == 0 or open_equity <= 0:
            return False
        current_weight = (quantity * raw_open) / open_equity
        return abs(current_weight - weights[symbol]) <= tolerance

    # Sell excess positions first, so every later purchase has settled cash available.
    for symbol, holding in holdings.items():
        raw_open = float(data[symbol].loc[index, "open"])
        if within_tolerance(symbol, raw_open, holding.quantity):
            continue
        target_value = open_equity * weights[symbol]
        excess_quantity = max(holding.quantity - floor(target_value / raw_open), 0)
        excess_quantity = (excess_quantity // lot) * lot
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
        if within_tolerance(symbol, raw_open, holding.quantity):
            continue
        target_value = open_equity * weights[symbol]
        current_value = holding.quantity * raw_open
        deficit_value = max(target_value - current_value, 0.0)
        fill_price = raw_open * (1 + strategy.costs.slippage_rate)
        unit_cost = fill_price * (1 + strategy.costs.commission_rate)
        quantity = min(floor(deficit_value / unit_cost), floor(cash / unit_cost))
        quantity = (quantity // lot) * lot
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

    if completed and strategy.rebalance.rebalance_cost:
        cash -= strategy.rebalance.rebalance_cost
        total_cost += strategy.rebalance.rebalance_cost

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
