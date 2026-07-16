from ..clients.openai_client import OpenAIStrategyClient
from ..schemas.strategy_parse_schema import StrategyParseResult


class StrategyParserService:
    def __init__(self, client: OpenAIStrategyClient | None = None) -> None:
        self.client = client or OpenAIStrategyClient()

    def parse(self, raw_input: str) -> StrategyParseResult:
        result = self.client.parse_strategy(raw_input)
        # This is a safety invariant even if a future client implementation changes.
        result.needs_confirmation = True
        return result
