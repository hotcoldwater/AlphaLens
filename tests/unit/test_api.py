from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.api import strategy_draft_routes
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
    assert body["total_cost"] == 0
    assert body["win_rate"] == 1
    assert body["average_holding_days"] == 1
    assert len(body["trades"]) == 1
    assert len(body["equity_curve"]) == 4
    assert body["trades"][0]["entry_date"] == "2024-01-03"
    result = client.get(f"/api/v1/backtests/{backtest_id}/result")
    assert result.status_code == 200
    assert result.json()["backtest_id"] == backtest_id


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


def test_backtest_result_returns_not_found_error():
    response = client.get("/api/v1/backtests/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "backtest not found",
        "details": [],
    }


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

    executed = client.post(
        f"/api/v1/strategy-drafts/{draft_id}/backtest",
        json={"data": bars()},
    )
    assert executed.status_code == 200
    assert executed.json()["trade_count"] == 1
