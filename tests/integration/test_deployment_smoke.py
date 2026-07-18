"""End-to-end checks against the actual FastAPI app, as opposed to unit tests
that exercise a single service/route in isolation. These are the checks a
deploy pipeline should run against a freshly booted instance before routing
traffic to it: is the process healthy, does a full chat -> confirm -> execute
lifecycle work, and is the error contract consistent across unrelated routes.
"""
from fastapi.testclient import TestClient

from services.api.app.api import strategy_draft_routes
from services.api.app.main import app
from services.api.app.schemas.strategy_parse_schema import StrategyParseResult
from tests.unit.test_api import api_strategy, bars

client = TestClient(app)


def test_health_endpoint_reports_a_live_database_connection():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database_connected"] is True
    assert response.headers["x-request-id"]


def test_full_strategy_lifecycle_parse_confirm_execute_retrieve(monkeypatch):
    parsed = StrategyParseResult(strategy=api_strategy())
    monkeypatch.setattr(strategy_draft_routes.parser_service, "parse", lambda _: parsed)

    draft = client.post(
        "/api/v1/strategy-drafts/parse", json={"raw_input": "삼성전자 SMA 교차 전략"},
    ).json()
    confirmed = client.post(f"/api/v1/strategy-drafts/{draft['draft_id']}/confirm").json()
    executed = client.post(
        f"/api/v1/strategy-drafts/{draft['draft_id']}/backtest", json={"data": bars()},
    ).json()

    retrieved = client.get(f"/api/v1/backtests/{executed['backtest_id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["strategy_id"] == confirmed["strategy_id"]

    library = client.get("/api/v1/strategies")
    assert any(item["strategy_id"] == confirmed["strategy_id"] for item in library.json()["strategies"])


def test_error_response_envelope_is_consistent_across_unrelated_routes():
    """404s, 422s, and 4xx business-rule rejections should all share the same
    {code, message, details} shape regardless of which route raised them."""
    not_found = client.get("/api/v1/backtests/does-not-exist")
    validation = client.post("/api/v1/backtests", json={"strategy": {}, "data": []})
    business_rule = client.post(
        "/api/v1/strategy-drafts/does-not-exist/backtest", json={"data": bars()},
    )

    for response, expected_status in ((not_found, 404), (validation, 422), (business_rule, 404)):
        assert response.status_code == expected_status
        body = response.json()
        assert set(body.keys()) == {"code", "message", "details"}
        assert isinstance(body["message"], str) and body["message"]
