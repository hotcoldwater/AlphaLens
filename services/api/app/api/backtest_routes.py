from fastapi import APIRouter, HTTPException

from ..enums import BacktestStatus
from ..schemas.backtest_schema import (
    BacktestRequest,
    BacktestResponse,
    EquityPoint,
    TradeResponse,
)
from ..services.backtest_service import execute_backtest
from ..services.backtest_store import backtest_store

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])


@router.post("", response_model=BacktestResponse)
def create_backtest(request: BacktestRequest) -> BacktestResponse:
    try:
        result = execute_backtest(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    response = BacktestResponse(
        backtest_id="pending",
        status=BacktestStatus.SUCCEEDED,
        initial_cash=result.initial_cash,
        final_equity=result.final_equity,
        total_return=result.total_return,
        cagr=result.cagr,
        max_drawdown=result.max_drawdown,
        volatility=result.volatility,
        sharpe_ratio=result.sharpe_ratio,
        win_rate=result.win_rate,
        average_trade_return=result.average_trade_return,
        average_holding_days=result.average_holding_days,
        total_cost=result.total_cost,
        trade_count=result.trade_count,
        trades=[
            TradeResponse(
                entry_date=trade.entry_date.date(),
                entry_price=trade.entry_price,
                exit_date=trade.exit_date.date(),
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                entry_cost=trade.entry_cost,
                exit_cost=trade.exit_cost,
                pnl=trade.pnl,
                return_rate=trade.return_rate,
                holding_days=trade.holding_days,
            )
            for trade in result.trades
        ],
        equity_curve=[
            EquityPoint(date=index.date(), equity=float(equity))
            for index, equity in result.equity_curve.items()
        ],
    )
    return backtest_store.save(response)


@router.get("/{backtest_id}/result", response_model=BacktestResponse)
def get_backtest_result(backtest_id: str) -> BacktestResponse:
    return backtest_store.get(backtest_id)


@router.get("/{backtest_id}", response_model=BacktestResponse)
def get_backtest(backtest_id: str) -> BacktestResponse:
    return backtest_store.get(backtest_id)
