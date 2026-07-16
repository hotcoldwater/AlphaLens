from fastapi import APIRouter, HTTPException

from ..clients.openai_client import OpenAIClientError
from ..enums import BacktestStatus
from ..schemas.backtest_explanation_schema import BacktestExplanation
from ..schemas.backtest_schema import (
    BacktestRequest,
    BacktestRunSummary,
    BacktestResponse,
    EquityPoint,
    StrategyBacktestListResponse,
    TradeResponse,
)
from ..services.backtest_service import execute_backtest
from ..services.backtest_explanation_service import BacktestExplanationService
from ..services.backtest_store import backtest_store

router = APIRouter(prefix="/api/v1/backtests", tags=["backtests"])
explanation_service = BacktestExplanationService()


@router.post("", response_model=BacktestResponse)
def create_backtest(request: BacktestRequest) -> BacktestResponse:
    try:
        result = execute_backtest(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return _to_response(request, result)


def _to_response(
    request: BacktestRequest,
    result=None,
    strategy_id: str | None = None,
    strategy_version: int | None = None,
) -> BacktestResponse:
    if result is None:
        try:
            result = execute_backtest(request)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    response = BacktestResponse(
        backtest_id="pending",
        status=BacktestStatus.SUCCEEDED,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        currency=request.strategy.capital.currency,
        data_version=result.data_version.identifier,
        data_start_date=result.data_version.start_date,
        data_end_date=result.data_version.end_date,
        data_points=result.data_version.point_count,
        benchmark_name="Same-data Buy & Hold",
        benchmark_total_return=result.benchmark_total_return,
        benchmark_max_drawdown=result.benchmark_max_drawdown,
        benchmark_equity_curve=[
            EquityPoint(date=index.date(), equity=float(equity))
            for index, equity in result.benchmark_equity_curve.items()
        ],
        initial_cash=result.result.initial_cash,
        final_equity=result.result.final_equity,
        total_return=result.result.total_return,
        cagr=result.result.cagr,
        max_drawdown=result.result.max_drawdown,
        volatility=result.result.volatility,
        sharpe_ratio=result.result.sharpe_ratio,
        win_rate=result.result.win_rate,
        average_trade_return=result.result.average_trade_return,
        average_holding_days=result.result.average_holding_days,
        total_cost=result.result.total_cost,
        trade_count=result.result.trade_count,
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
            for trade in result.result.trades
        ],
        equity_curve=[
            EquityPoint(date=index.date(), equity=float(equity))
            for index, equity in result.result.equity_curve.items()
        ],
    )
    return backtest_store.save(response)


@router.get("/{backtest_id}/result", response_model=BacktestResponse)
def get_backtest_result(backtest_id: str) -> BacktestResponse:
    return backtest_store.get(backtest_id)


@router.post("/{backtest_id}/explanation", response_model=BacktestExplanation)
def explain_backtest_result(backtest_id: str) -> BacktestExplanation:
    result = backtest_store.get(backtest_id)
    try:
        return explanation_service.explain(result)
    except OpenAIClientError as error:
        status_code = 503 if "not configured" in str(error) else 502
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.get("/{backtest_id}", response_model=BacktestResponse)
def get_backtest(backtest_id: str) -> BacktestResponse:
    return backtest_store.get(backtest_id)
