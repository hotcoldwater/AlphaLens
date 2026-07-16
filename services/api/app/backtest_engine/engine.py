from dataclasses import asdict, dataclass
from math import floor

import pandas as pd

from ..enums import PositionSizingMethod
from ..schemas.strategy_schema import Strategy
from .metrics import annualized_volatility, sharpe_ratio


@dataclass(frozen=True)
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    quantity: int
    entry_cost: float
    exit_cost: float
    pnl: float
    return_rate: float
    holding_days: int


@dataclass
class BacktestResult:
    initial_cash: float
    final_equity: float
    total_return: float
    cagr: float
    max_drawdown: float
    volatility: float
    sharpe_ratio: float
    win_rate: float
    average_trade_return: float
    average_holding_days: float
    total_cost: float
    trade_count: int
    trades: list[Trade]
    equity_curve: pd.Series

    def as_dict(self) -> dict:
        return {
            "initial_cash": self.initial_cash,
            "final_equity": self.final_equity,
            "total_return": self.total_return,
            "cagr": self.cagr,
            "max_drawdown": self.max_drawdown,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "average_trade_return": self.average_trade_return,
            "average_holding_days": self.average_holding_days,
            "total_cost": self.total_cost,
            "trade_count": self.trade_count,
            "trades": [
                {
                    **asdict(trade),
                    "entry_date": trade.entry_date.isoformat(),
                    "exit_date": trade.exit_date.isoformat(),
                }
                for trade in self.trades
            ],
            "equity_curve": self.equity_curve.to_dict(),
        }


def run_backtest(
    data: pd.DataFrame,
    entry_signal: pd.Series,
    exit_signal: pd.Series,
    strategy: Strategy,
) -> BacktestResult:
    """Run a long-only, single-stock backtest using next-session open fills."""
    _validate_inputs(data, entry_signal, exit_signal)
    initial_cash = float(strategy.capital.initial_cash)
    cash = initial_cash
    quantity = 0
    entry_date: pd.Timestamp | None = None
    entry_price = 0.0
    entry_cost = 0.0
    total_cost = 0.0
    trades: list[Trade] = []
    equity_values: list[float] = []
    commission = strategy.costs.commission_rate
    slippage = strategy.costs.slippage_rate
    tax = strategy.costs.tax_rate
    entry_orders = entry_signal.shift(1).eq(True)
    exit_orders = exit_signal.shift(1).eq(True)
    risk_exit_order = False

    for index, row in data.iterrows():
        # Signals are calculated after the previous close and executed today.
        if quantity == 0 and bool(entry_orders.loc[index]):
            fill_price = float(row["open"]) * (1 + slippage)
            quantity = _buy_quantity(cash, fill_price, strategy)
            if quantity:
                gross = quantity * fill_price
                entry_cost = gross * commission
                total_cost += entry_cost
                cash -= gross + entry_cost
                entry_date = index
                entry_price = fill_price
        elif quantity > 0 and (bool(exit_orders.loc[index]) or risk_exit_order):
            fill_price = float(row["open"]) * (1 - slippage)
            gross = quantity * fill_price
            exit_cost = gross * (commission + tax)
            total_cost += exit_cost
            cash += gross - exit_cost
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
                )
            )
            quantity = 0
            entry_date = None
            entry_price = 0.0
            entry_cost = 0.0
            risk_exit_order = False

        equity_values.append(cash + quantity * float(row["close"]))

        # Risk conditions are evaluated after this close, then filled at the next open.
        if quantity > 0:
            assert entry_date is not None
            risk_exit_order = _should_exit_for_risk(
                close=float(row["close"]),
                entry_price=entry_price,
                entry_date=entry_date,
                current_date=index,
                strategy=strategy,
            )

    equity_curve = pd.Series(equity_values, index=data.index, name="equity")
    final_equity = float(equity_curve.iloc[-1])
    total_return = final_equity / initial_cash - 1
    elapsed_days = max((data.index[-1] - data.index[0]).days, 1)
    cagr = (final_equity / initial_cash) ** (365.25 / elapsed_days) - 1
    drawdown = equity_curve / equity_curve.cummax() - 1
    trade_returns = [trade.return_rate for trade in trades]
    winning_trades = sum(return_rate > 0 for return_rate in trade_returns)
    return BacktestResult(
        initial_cash=initial_cash,
        final_equity=final_equity,
        total_return=float(total_return),
        cagr=float(cagr),
        max_drawdown=float(drawdown.min()),
        volatility=annualized_volatility(equity_curve),
        sharpe_ratio=sharpe_ratio(equity_curve),
        win_rate=winning_trades / len(trades) if trades else 0.0,
        average_trade_return=sum(trade_returns) / len(trades) if trades else 0.0,
        average_holding_days=(sum(trade.holding_days for trade in trades) / len(trades)) if trades else 0.0,
        total_cost=total_cost,
        trade_count=len(trades),
        trades=trades,
        equity_curve=equity_curve,
    )


def _buy_quantity(cash: float, price: float, strategy: Strategy) -> int:
    method = strategy.position_sizing.method
    if method == PositionSizingMethod.AVAILABLE_CASH:
        budget = cash
    elif method == PositionSizingMethod.PERCENT_OF_EQUITY:
        budget = cash * float(strategy.position_sizing.value)
    elif method == PositionSizingMethod.FIXED_AMOUNT:
        budget = min(cash, float(strategy.position_sizing.value))
    else:
        unit_cost = price * (1 + strategy.costs.commission_rate)
        return max(min(floor(float(strategy.position_sizing.value)), floor(cash / unit_cost)), 0)
    unit_cost = price * (1 + strategy.costs.commission_rate)
    return max(floor(budget / unit_cost), 0)


def _should_exit_for_risk(
    close: float,
    entry_price: float,
    entry_date: pd.Timestamp,
    current_date: pd.Timestamp,
    strategy: Strategy,
) -> bool:
    risk = strategy.risk_management
    if risk.stop_loss is not None and close <= entry_price * (1 - risk.stop_loss):
        return True
    if risk.take_profit is not None and close >= entry_price * (1 + risk.take_profit):
        return True
    return (
        risk.maximum_holding_days is not None
        and (current_date - entry_date).days >= risk.maximum_holding_days
    )


def _validate_inputs(data: pd.DataFrame, entry_signal: pd.Series, exit_signal: pd.Series) -> None:
    required_columns = {"open", "close"}
    if not required_columns.issubset(data.columns):
        raise ValueError("data must contain open and close columns")
    if data.empty:
        raise ValueError("data must not be empty")
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("data index must be a DatetimeIndex")
    if not data.index.is_monotonic_increasing or not data.index.is_unique:
        raise ValueError("data index must be sorted and unique")
    if not data.index.equals(entry_signal.index) or not data.index.equals(exit_signal.index):
        raise ValueError("signals must have the same index as data")
