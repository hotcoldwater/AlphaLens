import pytest

from services.api.app.api import strategy_draft_routes
from services.api.app.clients.openai_client import OpenAIClientError, OpenAIStrategyClient
from services.api.app.enums import BacktestStatus
from services.api.app.schemas.backtest_explanation_schema import BacktestExplanation
from services.api.app.schemas.backtest_schema import BacktestResponse
from services.api.app.schemas.strategy_parse_schema import StrategyParseResult
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


def test_openai_client_requires_api_key():
    with pytest.raises(OpenAIClientError, match="OPENAI_API_KEY"):
        OpenAIStrategyClient(api_key="").parse_strategy("전략")


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


def test_parse_endpoint_returns_draft_and_never_auto_confirms(monkeypatch):
    parsed = parsed_result()
    monkeypatch.setattr(strategy_draft_routes.parser_service, "parse", lambda _: parsed)

    response = strategy_draft_routes.parse_strategy(
        strategy_draft_routes.StrategyParseRequest(raw_input="전략")
    )

    assert response.needs_confirmation is True
    assert response.missing_fields == ["benchmark"]
