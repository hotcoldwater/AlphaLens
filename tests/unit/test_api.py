from fastapi.testclient import TestClient
import pytest

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


def regime_switch_strategy() -> dict:
    return {
        "strategy_type": "REGIME_SWITCH",
        "strategy_name": "SPY to GLD defensive switch",
        "market": "NASDAQ",
        "universe": {"type": "REGIME_SWITCH", "symbols": ["SPY", "GLD"]},
        "period": {"start_date": "2024-01-01", "end_date": "2024-01-04"},
        "default_symbol": "SPY",
        "switch_rule": {
            "signal_symbol": "SPY",
            "condition": {
                "left": {"indicator": "CLOSE"},
                "operator": "LESS_THAN",
                "right": {"indicator": "SMA", "period": 2},
            },
            "target_symbol": "GLD",
        },
        "capital": {"initial_cash": 10_000, "currency": "USD"},
    }


def allocation_rebalance_strategy() -> dict:
    return {
        "strategy_type": "ALLOCATION_REBALANCE",
        "strategy_name": "60/40 portfolio",
        "market": "NASDAQ",
        "universe": {"type": "ALLOCATION_REBALANCE", "symbols": ["SPY", "GLD"]},
        "period": {"start_date": "2024-01-31", "end_date": "2024-02-02"},
        "target_allocations": [
            {"symbol": "SPY", "weight": 0.6},
            {"symbol": "GLD", "weight": 0.4},
        ],
        "capital": {"initial_cash": 1000, "currency": "USD"},
    }


def allocation_bars(closes: list[float]) -> list[dict]:
    dates = ["2024-01-31", "2024-02-01", "2024-02-02"]
    return [
        {"date": date, "open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1000}
        for date, close in zip(dates, closes)
    ]


def test_backtest_endpoint_returns_symbol_attribution_for_allocation_rebalance():
    response = client.post(
        "/api/v1/backtests",
        json={
            "strategy": allocation_rebalance_strategy(),
            "data_by_symbol": {
                "SPY": allocation_bars([100, 200, 200]),
                "GLD": allocation_bars([100, 50, 50]),
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["symbol_attribution"] == [{
        "symbol": "SPY", "trade_count": 1, "total_pnl": body["trades"][0]["pnl"],
        "contribution_to_return": body["trades"][0]["pnl"] / 1000,
        "average_holding_days": body["trades"][0]["holding_days"],
    }]


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
    assert body["currency"] == "KRW"
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


def test_backtest_response_uses_strategy_currency():
    strategy = api_strategy()
    strategy["capital"]["currency"] = "USD"

    response = client.post("/api/v1/backtests", json={"strategy": strategy, "data": bars()})

    assert response.status_code == 200
    assert response.json()["currency"] == "USD"


def test_backtest_persists_market_data_provenance():
    response = client.post("/api/v1/backtests", json={
        "strategy": api_strategy(),
        "data": bars(),
        "data_sources": [{
            "symbol": "NVDA",
            "provider": "YFINANCE",
            "adjustment": "Yahoo Finance auto-adjusted daily OHLCV",
            "data_version": "sha256:provider-input",
            "collected_at": "2026-07-17T08:00:00Z",
        }],
    })

    assert response.status_code == 200
    assert response.json()["data_sources"][0]["symbol"] == "NVDA"
    saved = client.get(f"/api/v1/backtests/{response.json()['backtest_id']}/result")
    assert saved.json()["data_sources"] == response.json()["data_sources"]


def test_backtest_endpoint_runs_two_asset_regime_switch():
    spy = bars()
    spy[1]["close"] = 90
    spy[2]["close"] = 110
    spy[1]["low"] = 89
    spy[2]["high"] = 111
    response = client.post(
        "/api/v1/backtests",
        json={
            "strategy": regime_switch_strategy(),
            "data_by_symbol": {"SPY": spy, "GLD": bars()},
        },
    )

    assert response.status_code == 200
    assert response.json()["currency"] == "USD"
    assert response.json()["benchmark_name"] == "Same-data Buy & Hold (SPY)"
    assert response.json()["trades"][0]["symbol"] == "SPY"


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


def test_api_standardizes_unexpected_non_value_errors(monkeypatch):
    # Starlette's ServerErrorMiddleware re-raises after building the response so
    # TestClient can surface bugs during testing; raise_server_exceptions=False
    # here asserts what a real client actually receives over the wire.
    def boom(request):
        raise KeyError("simulated engine bug")

    monkeypatch.setattr(backtest_routes, "execute_backtest", boom)
    non_raising_client = TestClient(app, raise_server_exceptions=False)
    response = non_raising_client.post("/api/v1/backtests", json={"strategy": api_strategy(), "data": bars()})

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.json()["message"] == "unexpected server error"


def test_api_responses_include_a_request_id_header():
    response = client.get("/health")
    assert response.headers["x-request-id"]


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
        provider="FMP", symbol="NVDA", adjustment="FMP dividend-adjusted EOD OHLCV",
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


@pytest.mark.parametrize("provider", ["YFINANCE", "PYKRX"])
def test_market_data_endpoint_accepts_personal_providers(monkeypatch, provider):
    import pandas as pd

    data = pd.DataFrame(bars()).assign(date=lambda frame: pd.to_datetime(frame["date"])).set_index("date")
    version = build_data_version(data)
    expected = MarketDataFetch(
        provider=provider, symbol="005930" if provider == "PYKRX" else "NVDA",
        adjustment="test adjustment", data=data, data_version=version,
    )
    monkeypatch.setattr(market_data_routes.market_data_service, "fetch", lambda **_: expected)

    response = client.post("/api/v1/market-data/daily-ohlcv", json={
        "provider": provider,
        "symbol": expected.symbol,
        "start_date": "2024-01-01",
        "end_date": "2024-01-04",
        "adjusted_price": True,
    })

    assert response.status_code == 200
    assert response.json()["provider"] == provider


def test_market_data_endpoint_rejects_invalid_provider_symbol_and_date_range():
    invalid_krx = client.post("/api/v1/market-data/daily-ohlcv", json={
        "provider": "PYKRX", "symbol": "SAMSUNG", "start_date": "2024-01-01",
        "end_date": "2024-01-04", "adjusted_price": True,
    })
    assert invalid_krx.status_code == 422
    assert "six-digit KRX ticker" in invalid_krx.json()["details"][0]["msg"]

    invalid_period = client.post("/api/v1/market-data/daily-ohlcv", json={
        "provider": "YFINANCE", "symbol": "NVDA", "start_date": "2024-02-01",
        "end_date": "2024-01-04", "adjusted_price": True,
    })
    assert invalid_period.status_code == 422
    assert "start_date" in invalid_period.json()["details"][0]["msg"]


def test_market_symbol_search_endpoint_returns_provider_results(monkeypatch):
    from services.api.app.services.market_data_service import MarketSymbol

    monkeypatch.setattr(
        market_data_routes.market_data_service,
        "search_symbols",
        lambda provider, query, limit: [MarketSymbol(provider, "005930", "삼성전자")],
    )
    response = client.get("/api/v1/market-data/symbols/search?provider=PYKRX&query=%EC%82%BC%EC%84%B1")

    assert response.status_code == 200
    assert response.json() == [{"provider": "PYKRX", "symbol": "005930", "name": "삼성전자"}]


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


def _confirmed_draft_id(monkeypatch) -> str:
    parsed = StrategyParseResult(strategy=api_strategy())
    monkeypatch.setattr(strategy_draft_routes.parser_service, "parse", lambda _: parsed)
    draft_response = client.post(
        "/api/v1/strategy-drafts/parse", json={"raw_input": "삼성전자 SMA 교차 전략"},
    )
    draft_id = draft_response.json()["draft_id"]
    client.post(f"/api/v1/strategy-drafts/{draft_id}/confirm")
    return draft_id


def test_draft_backtest_rejects_concurrent_duplicate_execution(monkeypatch):
    from services.api.app.services.execution_guard import backtest_execution_guard

    draft_id = _confirmed_draft_id(monkeypatch)
    assert backtest_execution_guard.acquire(draft_id)
    try:
        response = client.post(f"/api/v1/strategy-drafts/{draft_id}/backtest", json={"data": bars()})
        assert response.status_code == 409
        assert "이미 실행 중" in response.json()["message"]
    finally:
        backtest_execution_guard.release(draft_id)

    # The guard is released after a failed/duplicate attempt, so a real request
    # immediately afterwards succeeds rather than being permanently locked out.
    retry = client.post(f"/api/v1/strategy-drafts/{draft_id}/backtest", json={"data": bars()})
    assert retry.status_code == 200


def test_failed_backtest_execution_is_recorded_and_listed(monkeypatch):
    draft_id = _confirmed_draft_id(monkeypatch)
    strategy_id = client.get(f"/api/v1/strategy-drafts/{draft_id}").json()["strategy_id"]

    def boom(request):
        raise ValueError("no market data exists within strategy period")

    monkeypatch.setattr(backtest_routes, "execute_backtest", boom)
    failed = client.post(f"/api/v1/strategy-drafts/{draft_id}/backtest", json={"data": bars()})
    assert failed.status_code == 400

    failures = client.get(f"/api/v1/strategies/{strategy_id}/failures")
    assert failures.status_code == 200
    assert failures.json()["failures"][0]["error_message"] == "no market data exists within strategy period"
    assert failures.json()["failures"][0]["draft_id"] == draft_id


def test_draft_backtest_accepts_data_sources_from_provider_fetch(monkeypatch):
    parsed = StrategyParseResult(strategy=api_strategy())
    monkeypatch.setattr(strategy_draft_routes.parser_service, "parse", lambda _: parsed)

    draft_response = client.post(
        "/api/v1/strategy-drafts/parse", json={"raw_input": "삼성전자 SMA 교차 전략"},
    )
    draft_id = draft_response.json()["draft_id"]
    client.post(f"/api/v1/strategy-drafts/{draft_id}/confirm")

    executed = client.post(
        f"/api/v1/strategy-drafts/{draft_id}/backtest",
        json={
            "data": bars(),
            "data_sources": [{
                "symbol": "005930", "provider": "PYKRX", "adjustment": "adjusted",
                "data_version": "sha256:test", "collected_at": "2024-01-01T00:00:00Z",
            }],
        },
    )
    assert executed.status_code == 200
