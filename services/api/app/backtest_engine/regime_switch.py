from dataclasses import dataclass
from math import floor

import pandas as pd

from ..schemas.strategy_schema import RegimeSwitchStrategy
from .engine import BacktestResult, Trade
from .metrics import annualized_volatility, sharpe_ratio
from .signal_generator import evaluate_condition


def run_regime_switch_backtest(
    data_by_symbol: dict[str, pd.DataFrame], strategy: RegimeSwitchStrategy
) -> BacktestResult:
    """Run a two-asset, all-in regime switch with next-common-session-open fills."""
    aligned = _align_data(data_by_symbol, strategy)
    signal_data = aligned[strategy.switch_rule.signal_symbol]
    active_regime = evaluate_condition(signal_data, strategy.switch_rule.condition)
    target_orders = pd.Series(strategy.default_symbol, index=signal_data.index, dtype="object")
    target_orders.loc[active_regime.shift(1, fill_value=False).astype(bool)] = strategy.switch_rule.target_symbol

    cash = float(strategy.capital.initial_cash)
    initial_cash = cash
    held_symbol: str | None = None
    quantity = 0
    entry_date: pd.Timestamp | None = None
    entry_price = 0.0
    entry_cost = 0.0
    total_cost = 0.0
    trades: list[Trade] = []
    equity_values: list[float] = []

    for index in signal_data.index:
        target_symbol = str(target_orders.loc[index])
        if held_symbol != target_symbol:
            if held_symbol is not None and quantity:
                sell_row = aligned[held_symbol].loc[index]
                fill_price = float(sell_row["open"]) * (1 - strategy.costs.slippage_rate)
                gross = quantity * fill_price
                exit_cost = gross * (strategy.costs.commission_rate + strategy.costs.tax_rate)
                cash += gross - exit_cost
                total_cost += exit_cost
                assert entry_date is not None
                invested = quantity * entry_price + entry_cost
                trades.append(
                    Trade(
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_date=index,
                        exit_price=fill_price,
                        quantity=quantity,
                        entry_cost=entry_cost,
                        exit_cost=exit_cost,
                        pnl=gross - exit_cost - invested,
                        return_rate=(gross - exit_cost - invested) / invested,
                        holding_days=(index - entry_date).days,
                        symbol=held_symbol,
                    )
                )
                quantity = 0
                held_symbol = None
                entry_date = None
                entry_price = 0.0
                entry_cost = 0.0

            buy_row = aligned[target_symbol].loc[index]
            fill_price = float(buy_row["open"]) * (1 + strategy.costs.slippage_rate)
            unit_cost = fill_price * (1 + strategy.costs.commission_rate)
            quantity = floor(cash / unit_cost)
            if quantity:
                gross = quantity * fill_price
                entry_cost = gross * strategy.costs.commission_rate
                cash -= gross + entry_cost
                total_cost += entry_cost
                held_symbol = target_symbol
                entry_date = index
                entry_price = fill_price

        close = float(aligned[held_symbol].loc[index, "close"]) if held_symbol else 0.0
        equity_values.append(cash + quantity * close)

    equity_curve = pd.Series(equity_values, index=signal_data.index, name="equity")
    final_equity = float(equity_curve.iloc[-1])
    total_return = final_equity / initial_cash - 1
    elapsed_days = max((equity_curve.index[-1] - equity_curve.index[0]).days, 1)
    trade_returns = [trade.return_rate for trade in trades]
    return BacktestResult(
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return=float(total_return),
        cagr=float((final_equity / initial_cash) ** (365.25 / elapsed_days) - 1),
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


def _align_data(
    data_by_symbol: dict[str, pd.DataFrame], strategy: RegimeSwitchStrategy
) -> dict[str, pd.DataFrame]:
    normalized = {symbol.upper(): frame.copy() for symbol, frame in data_by_symbol.items()}
    common_index: pd.DatetimeIndex | None = None
    for symbol in strategy.universe.symbols:
        if symbol not in normalized:
            raise ValueError(f"missing market data for {symbol}")
        index = normalized[symbol].index
        common_index = index if common_index is None else common_index.intersection(index)
    assert common_index is not None
    common_index = common_index.sort_values()
    if len(common_index) < 2:
        counts = ", ".join(f"{symbol}: {len(normalized[symbol])}개" for symbol in strategy.universe.symbols)
        raise ValueError(
            "REGIME_SWITCH requires at least two common trading dates "
            f"(found {len(common_index)}; supplied data points — {counts})"
        )
    return {symbol: normalized[symbol].loc[common_index] for symbol in strategy.universe.symbols}
