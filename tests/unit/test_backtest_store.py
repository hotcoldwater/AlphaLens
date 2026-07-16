from services.api.app.enums import BacktestStatus
from services.api.app.schemas.backtest_schema import BacktestResponse
from services.api.app.services.backtest_store import BacktestStore


def test_backtest_result_survives_store_recreation(monkeypatch, tmp_path):
    monkeypatch.setenv("ALPHALENS_DATABASE_PATH", str(tmp_path / "alphalens.db"))
    response = BacktestResponse(
        backtest_id="pending",
        status=BacktestStatus.SUCCEEDED,
        initial_cash=1000,
        final_equity=1100,
        total_return=0.1,
        cagr=0.1,
        max_drawdown=0,
        volatility=0,
        sharpe_ratio=0,
        win_rate=1,
        average_trade_return=0.1,
        average_holding_days=2,
        total_cost=1,
        trade_count=1,
        trades=[],
        equity_curve=[],
    )

    first_store = BacktestStore()
    saved = first_store.save(response)
    loaded = BacktestStore().get(saved.backtest_id)

    assert loaded.backtest_id == saved.backtest_id
    assert loaded.final_equity == 1100
    assert loaded.status == BacktestStatus.SUCCEEDED
