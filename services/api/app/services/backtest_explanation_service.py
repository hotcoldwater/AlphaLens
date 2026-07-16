from ..clients.openai_client import OpenAIStrategyClient
from ..schemas.backtest_explanation_schema import BacktestExplanation
from ..schemas.backtest_schema import BacktestResponse


class BacktestExplanationService:
    def __init__(self, client: OpenAIStrategyClient | None = None) -> None:
        self.client = client or OpenAIStrategyClient()

    def explain(self, result: BacktestResponse) -> BacktestExplanation:
        # The client receives only already-calculated output, never price data or executable rules.
        return self.client.explain_backtest(result)
