import os

from openai import OpenAI

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
            response = self._client.responses.parse(
                model=self.model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": raw_input},
                ],
                text_format=StrategyParseResult,
            )
        except Exception as error:
            raise OpenAIClientError("OpenAI strategy parsing failed") from error
        if response.output_parsed is None:
            raise OpenAIClientError("OpenAI returned no structured strategy")
        return response.output_parsed
