import pytest

from services.api.app.api import strategy_draft_routes
from services.api.app.clients.openai_client import OpenAIClientError, OpenAIStrategyClient
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


def test_openai_client_requires_api_key():
    with pytest.raises(OpenAIClientError, match="OPENAI_API_KEY"):
        OpenAIStrategyClient(api_key="").parse_strategy("전략")


def test_parse_endpoint_returns_draft_and_never_auto_confirms(monkeypatch):
    parsed = parsed_result()
    monkeypatch.setattr(strategy_draft_routes.parser_service, "parse", lambda _: parsed)

    response = strategy_draft_routes.parse_strategy(
        strategy_draft_routes.StrategyParseRequest(raw_input="전략")
    )

    assert response.needs_confirmation is True
    assert response.missing_fields == ["benchmark"]
