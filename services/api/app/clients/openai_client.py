import os
from datetime import date

from openai import OpenAI

from ..schemas.backtest_explanation_schema import BacktestExplanation
from ..schemas.backtest_schema import BacktestResponse
from ..schemas.strategy_parse_schema import StrategyParseResult


SYSTEM_PROMPT = """You convert Korean or English natural-language investment strategies into the supplied Strategy schema.

Rules:
- Return only fields supported by the schema. Never return Python code.
- Use only the enum values and indicators/operators in the schema.
- Preserve explicit user values.
- Put omitted user inputs in missing_fields and values selected by a safe default in assumptions.
- Default execution is CLOSE signal and NEXT_OPEN execution.
- Default market is KRX, daily timeframe, adjusted prices, and KRW.
- The result is a draft only. It must always require user confirmation before execution.
- If the request cannot be represented by the schema, explain it in warnings and use no unsupported feature.
"""

EXPLANATION_SYSTEM_PROMPT = """You explain fixed backtest results in Korean.

Rules:
- Use only the supplied values. Do not calculate, change, infer, or fabricate metrics.
- Do not make predictions, price targets, buy/sell recommendations, or personalized financial advice.
- Explain that the Buy & Hold reference uses the same supplied OHLCV data when it is present.
- Distinguish observed results from limitations and risks.
- Keep the tone concise and factual.
- The disclaimer must state that this is historical backtest interpretation, not investment advice.
"""


class OpenAIClientError(RuntimeError):
    pass


class OpenAIStrategyClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6")
        self._client: OpenAI | None = None

    def parse_strategy(self, raw_input: str) -> StrategyParseResult:
        if not self.api_key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        try:
            system_prompt = (
                f"{SYSTEM_PROMPT}\n"
                f"Today's date is {date.today().isoformat()}. Use this date when the user says 'today', 'now', or 'until present'."
            )
            response = self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_input},
                ],
                text_format=StrategyParseResult,
            )
        except Exception as error:
            raise OpenAIClientError("OpenAI strategy parsing failed") from error
        if response.output_parsed is None:
            raise OpenAIClientError("OpenAI returned no structured strategy")
        return response.output_parsed

    def explain_backtest(self, result: BacktestResponse) -> BacktestExplanation:
        if not self.api_key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        payload = {
            "data_period": [str(result.data_start_date), str(result.data_end_date)],
            "data_points": result.data_points,
            "total_return": result.total_return,
            "cagr": result.cagr,
            "max_drawdown": result.max_drawdown,
            "volatility": result.volatility,
            "sharpe_ratio": result.sharpe_ratio,
            "win_rate": result.win_rate,
            "trade_count": result.trade_count,
            "average_holding_days": result.average_holding_days,
            "total_cost": result.total_cost,
            "benchmark_name": result.benchmark_name,
            "benchmark_total_return": result.benchmark_total_return,
            "benchmark_max_drawdown": result.benchmark_max_drawdown,
        }
        try:
            response = self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": EXPLANATION_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Explain this fixed backtest result: {payload}"},
                ],
                text_format=BacktestExplanation,
            )
        except Exception as error:
            raise OpenAIClientError("OpenAI backtest explanation failed") from error
        if response.output_parsed is None:
            raise OpenAIClientError("OpenAI returned no structured explanation")
        return response.output_parsed
