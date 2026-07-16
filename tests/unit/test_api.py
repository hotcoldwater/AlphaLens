from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.api import backtest_routes, market_data_routes, strategy_draft_routes
from services.api.app.backtest_engine.market_data import build_data_version
from services.api.app.services.market_data_service import MarketDataFetch
from services.api.app.schemas.backtest_explanation_schema import BacktestExplanation
from services.api.app.schemas.strategy_parse_schema import StrategyParseResult
from tests.unit.test_strategy_schema import valid_strategy


client = TestClient(app)


def api_strategy() -> dict:
    payload = valid_strategy()
    payload["entry_rules"] = {
        "conditions": [{"left": {"indicator": "CLOSE"}, "operator": "GREATER_THAN", "right": {"value": 100}}]
    }
    payload["exit_rules"] = {
        "conditions": [{"left": {"indicator": "CLOSE"}, "operator": "LESS_THAN", "right": {"value": 100}}]
    }
    payload["position_sizing"] = {"method": "AVAILABLE_CASH"}
    payload["capital"] = {"initial_cash": 10_000}
    return payload


def bars() -> list[dict]:
    return [
        {"date": "2024-01-01", "open": 100, "high": 102, "low": 98, "close": 100, "volume": 1000},
        {"date": "2024-01-02", "open": 101, "high": 103, "low": 99, "close": 101, "volume": 1000},
        {"date": "2024-01-03", "open": 98, "high": 100, "low": 96, "close": 99, "volume": 1000},
        {"date": "2024-01-04", "open": 99, "high": 101, "low": 97, "close": 100, "volume": 1000},
    ]


def test_strategy_validation_endpoint():
    response = client.post("/api/v1/strategies/validate", json=api_strategy())
    assert response.status_code == 200
    assert response.json()["valid"] is True

    invalid = {**api_strategy(), "period": {"start_date": "2025-01-01", "end_date": "2024-01-01"}}
    response = client.post("/api/v1/strategies/validate", json=invalid)
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["errors"]


def test_backtest_endpoint_runs_engine_and_returns_response_schema():
    response = client.post("/api/v1/backtests", json={"strategy": api_strategy(), "data": bars()})
    body = response.json()

    assert response.status_code == 200
    backtest_id = body["backtest_id"]
    assert body["status"] == "SUCCEEDED"
    assert body["trade_count"] == 1
    assert body["data_version"].startswith("sha256:")
    assert body["data_points"] == 4
    assert body["data_start_date"] == "2024-01-01"
    assert body["data_end_date"] == "2024-01-04"
    assert body["benchmark_name"] == "Same-data Buy & Hold"
    assert body["benchmark_total_return"] == 0
    assert len(body["benchmark_equity_curve"]) == 4
    assert body["total_cost"] == 0
    assert body["win_rate"] == 1
    assert body["average_holding_days"] == 1
    assert len(body["trades"]) == 1
    assert len(body["equity_curve"]) == 4
    assert body["trades"][0]["entry_date"] == "2024-01-03"
    result = client.get(f"/api/v1/backtests/{backtest_id}/result")
    assert result.status_code == 200
    assert result.json()["backtest_id"] == backtest_id
    assert result.json()["data_version"] == body["data_version"]


def test_backtest_endpoint_is_reproducible_for_same_strategy_and_data():
    first = client.post("/api/v1/backtests", json={"strategy": api_strategy(), "data": bars()})
    second = client.post("/api/v1/backtests", json={"strategy": api_strategy(), "data": bars()})

    assert first.status_code == second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    for field in ("data_version", "final_equity", "total_return", "max_drawdown", "trade_count", "trades", "equity_curve"):
        assert first_body[field] == second_body[field]


def test_backtest_endpoint_rejects_data_outside_strategy_period():
    strategy = api_strategy()
    strategy["period"] = {"start_date": "2025-01-01", "end_date": "2025-01-31"}
    response = client.post("/api/v1/backtests", json={"strategy": strategy, "data": bars()})
    assert response.status_code == 400
    assert response.json()["code"] == "HTTP_ERROR"
    assert "no market data" in response.json()["message"]


def test_api_returns_standard_validation_errors():
    response = client.post("/api/v1/backtests", json={"strategy": {}, "data": []})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["details"]


def test_api_allows_local_web_client_cors_preflight():
    response = client.options(
        "/api/v1/backtests/example",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_market_data_endpoint_returns_normalized_provider_data(monkeypatch):
    import pandas as pd

    data = pd.DataFrame(bars()).assign(date=lambda frame: pd.to_datetime(frame["date"])).set_index("date")
    version = build_data_version(data)
    expected = MarketDataFetch(
        provider="FMP", symbol="NVDA", adjustment="FMP adjusted with adjClose factor",
        data=data, data_version=version,
    )
    monkeypatch.setattr(market_data_routes.market_data_service, "fetch", lambda **_: expected)

    response = client.post("/api/v1/market-data/daily-ohlcv", json={
        "provider": "FMP", "symbol": "nvda", "start_date": "2024-01-01", "end_date": "2024-01-04", "adjusted_price": True,
    })

    assert response.status_code == 200
    assert response.json()["symbol"] == "NVDA"
    assert response.json()["data_version"] == version.identifier
    assert response.json()["data_points"] == 4


def test_backtest_result_returns_not_found_error():
    response = client.get("/api/v1/backtests/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "backtest not found",
        "details": [],
    }


def test_backtest_explanation_uses_saved_result(monkeypatch):
    created = client.post("/api/v1/backtests", json={"strategy": api_strategy(), "data": bars()})
    backtest_id = created.json()["backtest_id"]
    expected = BacktestExplanation(
        summary="고정된 결과입니다.", strengths=[], risks=["표본 제한"], observations=[],
        disclaimer="과거 백테스트 해석이며 투자 조언이 아닙니다.",
    )
    monkeypatch.setattr(backtest_routes.explanation_service, "explain", lambda result: expected)

    response = client.post(f"/api/v1/backtests/{backtest_id}/explanation")

    assert response.status_code == 200
    assert response.json()["summary"] == "고정된 결과입니다."


def test_draft_requires_confirmation_before_backtest(monkeypatch):
    parsed = StrategyParseResult(strategy=api_strategy())
    monkeypatch.setattr(strategy_draft_routes.parser_service, "parse", lambda _: parsed)

    draft_response = client.post(
        "/api/v1/strategy-drafts/parse",
        json={"raw_input": "삼성전자 SMA 교차 전략"},
    )
    assert draft_response.status_code == 200
    draft = draft_response.json()
    draft_id = draft["draft_id"]
    assert draft["status"] == "READY_TO_CONFIRM"
    assert draft["needs_confirmation"] is True

    blocked = client.post(
        f"/api/v1/strategy-drafts/{draft_id}/backtest",
        json={"data": bars()},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "HTTP_ERROR"

    confirmed = client.post(f"/api/v1/strategy-drafts/{draft_id}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"
    assert confirmed.json()["version"] == 1
    strategy_id = confirmed.json()["strategy_id"]
    versions = client.get(f"/api/v1/strategies/{strategy_id}/versions")
    assert versions.status_code == 200
    assert versions.json()["versions"][0]["version"] == 1
    library = client.get("/api/v1/strategies")
    assert library.status_code == 200
    assert any(item["strategy_id"] == strategy_id for item in library.json()["strategies"])
    clone = client.post(f"/api/v1/strategies/{strategy_id}/versions/1/clone")
    assert clone.status_code == 200
    assert clone.json()["status"] == "READY_TO_CONFIRM"
    assert clone.json()["strategy"] == confirmed.json()["strategy"]
    cloned_confirmation = client.post(f"/api/v1/strategy-drafts/{clone.json()['draft_id']}/confirm")
    assert cloned_confirmation.status_code == 200
    assert cloned_confirmation.json()["strategy_id"] == strategy_id
    assert cloned_confirmation.json()["version"] == 2

    executed = client.post(
        f"/api/v1/strategy-drafts/{draft_id}/backtest",
        json={"data": bars()},
    )
    assert executed.status_code == 200
    assert executed.json()["trade_count"] == 1
    assert executed.json()["strategy_id"] == strategy_id
    strategy_runs = client.get(f"/api/v1/strategies/{strategy_id}/backtests")
    assert strategy_runs.status_code == 200
    assert strategy_runs.json()["runs"][0]["backtest_id"] == executed.json()["backtest_id"]
