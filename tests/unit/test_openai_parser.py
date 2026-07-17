import pytest

from services.api.app.api import strategy_draft_routes
from services.api.app.clients.openai_client import OpenAIClientError, OpenAIStrategyClient
from services.api.app.services.strategy_parser_service import StrategyParserService
from services.api.app.enums import BacktestStatus
from services.api.app.schemas.backtest_explanation_schema import BacktestExplanation
from services.api.app.schemas.backtest_schema import BacktestResponse
from services.api.app.schemas.strategy_parse_schema import StrategyParseResult
from services.api.app.schemas.strategy_schema import AllocationRebalanceStrategy
from tests.unit.test_strategy_schema import valid_strategy


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_parsed": self.parsed})()


def parsed_result() -> StrategyParseResult:
    return StrategyParseResult(
        strategy=valid_strategy(),
        missing_fields=["benchmark"],
        assumptions=["Defaulted execution to next open"],
    )


def test_openai_client_uses_pydantic_structured_output():
    client = OpenAIStrategyClient(api_key="test-key", model="test-model")
    responses = FakeResponses(parsed_result())
    client._client = type("FakeClient", (), {"responses": responses})()

    result = client.parse_strategy("삼성전자 이동평균 전략")

    assert result.strategy.strategy_name == "Sample SMA strategy"
    assert responses.calls[0]["model"] == "test-model"
    assert responses.calls[0]["text_format"] is StrategyParseResult
    assert "Today's date is " in responses.calls[0]["input"][0]["content"]
    assert "market NASDAQ" in responses.calls[0]["input"][0]["content"]
    assert "USD capital" in responses.calls[0]["input"][0]["content"]


def test_openai_client_requires_api_key():
    with pytest.raises(OpenAIClientError, match="OPENAI_API_KEY"):
        OpenAIStrategyClient(api_key="").parse_strategy("전략")


def test_openai_client_trims_configured_api_key_whitespace():
    client = OpenAIStrategyClient(api_key=" test-key\n", model="test-model")

    assert client.api_key == "test-key"


def test_openai_client_returns_safe_error_type_when_parsing_fails():
    client = OpenAIStrategyClient(api_key="test-key", model="test-model")

    class FailedResponses:
        def parse(self, **kwargs):
            raise RuntimeError("network detail must not be exposed")

    client._client = type("FakeClient", (), {"responses": FailedResponses()})()

    with pytest.raises(OpenAIClientError, match=r"RuntimeError\)"):
        client.parse_strategy("전략")


def test_parser_does_not_silently_replace_asset_switch_with_cash_strategy():
    class SingleStockClient:
        def parse_strategy(self, raw_input: str) -> StrategyParseResult:
            return parsed_result()

    result = StrategyParserService(client=SingleStockClient()).parse(
        "SPY가 30일 SMA 아래면 GLD로 전환해줘"
    )

    assert result.needs_clarification is True
    assert any("자동 변경하지 않습니다" in warning for warning in result.warnings)


def test_parser_allows_allocation_strategy_even_when_request_mentions_switching():
    allocation = AllocationRebalanceStrategy.model_validate({
        "strategy_type": "ALLOCATION_REBALANCE",
        "strategy_name": "NVDA GLD monthly allocation",
        "market": "NASDAQ",
        "universe": {"type": "ALLOCATION_REBALANCE", "symbols": ["NVDA", "GLD"]},
        "period": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
        "target_allocations": [{"symbol": "NVDA", "weight": 0.7}, {"symbol": "GLD", "weight": 0.3}],
        "rebalance": {"frequency": "MONTHLY"},
        "capital": {"initial_cash": 10_000, "currency": "USD"},
    })

    class AllocationClient:
        def parse_strategy(self, raw_input: str) -> StrategyParseResult:
            return StrategyParseResult(strategy=allocation, needs_clarification=True)

    result = StrategyParserService(client=AllocationClient()).parse(
        "NVDA와 GLD 비중을 매월 전환해줘"
    )

    assert result.needs_clarification is False


def test_parser_blocks_index_signal_that_would_be_applied_to_a_different_stock():
    class SingleStockClient:
        def parse_strategy(self, raw_input: str) -> StrategyParseResult:
            return parsed_result()

    result = StrategyParserService(client=SingleStockClient()).parse(
        "KOSPI가 전일 대비 하락하면 삼성전자를 매수하고 상승하면 매도해줘"
    )

    assert result.needs_clarification is True
    assert any("별도 지수" in warning for warning in result.warnings)


def test_openai_client_explains_fixed_result_with_structured_output():
    client = OpenAIStrategyClient(api_key="test-key", model="test-model")
    explanation = BacktestExplanation(
        summary="고정된 결과 요약",
        strengths=["거래 비용이 낮습니다."],
        risks=["표본 기간이 제한적입니다."],
        observations=["Buy & Hold와 비교합니다."],
        disclaimer="과거 백테스트 해석이며 투자 조언이 아닙니다.",
    )
    responses = FakeResponses(explanation)
    client._client = type("FakeClient", (), {"responses": responses})()
    result = BacktestResponse(
        backtest_id="run", status=BacktestStatus.SUCCEEDED, initial_cash=1000,
        final_equity=1100, total_return=0.1, cagr=0.1, max_drawdown=-0.1,
        volatility=0.2, sharpe_ratio=1, win_rate=0.5, average_trade_return=0.1,
        average_holding_days=2, total_cost=1, trade_count=1, trades=[], equity_curve=[],
    )

    parsed = client.explain_backtest(result)

    assert parsed.summary == "고정된 결과 요약"
    assert responses.calls[0]["text_format"] is BacktestExplanation
    assert "Do not calculate" in responses.calls[0]["input"][0]["content"]
    assert "10.00%" in responses.calls[0]["input"][1]["content"]


def test_parse_endpoint_returns_draft_and_never_auto_confirms(monkeypatch):
    parsed = parsed_result()
    monkeypatch.setattr(strategy_draft_routes.parser_service, "parse", lambda _: parsed)

    response = strategy_draft_routes.parse_strategy(
        strategy_draft_routes.StrategyParseRequest(raw_input="전략")
    )

    assert response.needs_confirmation is True
    assert response.missing_fields == ["benchmark"]
