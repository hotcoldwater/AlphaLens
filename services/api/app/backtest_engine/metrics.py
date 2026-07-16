from math import sqrt

import pandas as pd


def annualized_volatility(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    returns = equity_curve.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    return float(returns.std(ddof=1) * sqrt(periods_per_year))


def sharpe_ratio(
    equity_curve: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    returns = equity_curve.pct_change().dropna()
    if len(returns) < 2:
        return 0.0
    daily_risk_free = (1 + risk_free_rate) ** (1 / periods_per_year) - 1
    excess_returns = returns - daily_risk_free
    standard_deviation = excess_returns.std(ddof=1)
    if standard_deviation == 0:
        return 0.0
    return float(excess_returns.mean() / standard_deviation * sqrt(periods_per_year))


def buy_and_hold_equity_curve(close: pd.Series, initial_cash: float) -> pd.Series:
    """Create a same-data Buy & Hold reference curve for strategy comparison."""
    if close.empty:
        raise ValueError("close prices must not be empty")
    normalized = close.astype(float) / float(close.iloc[0])
    return normalized * initial_cash


def maximum_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    return float((equity_curve / equity_curve.cummax() - 1).min())
