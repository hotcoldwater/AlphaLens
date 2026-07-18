import os
import logging
from datetime import date

from openai import OpenAI

from ..schemas.backtest_explanation_schema import BacktestExplanation
from ..schemas.backtest_schema import BacktestResponse
from ..schemas.strategy_parse_schema import StrategyParseResult


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You convert Korean or English natural-language investment strategies into the supplied Strategy schema.

Rules:
- Return only fields supported by the schema. Never return Python code.
- Use only the enum values and indicators/operators in the schema.
- Preserve explicit user values.
- Put omitted user inputs in missing_fields and values selected by a safe default in assumptions.
- Default execution is CLOSE signal and NEXT_OPEN execution.
- For explicit NASDAQ or US stock requests, use market NASDAQ, the US ticker symbol
  (for example NVDA or AAPL), daily adjusted prices, and USD capital.
- Default market is KRX, daily timeframe, adjusted prices, and KRW only when the
  user does not specify a market or a US stock.
- The result is a draft only. It must always require user confirmation before execution.
- For a single-stock strategy whose entry/exit condition is signaled by a different symbol
  (for example "buy Samsung Electronics when the KOSPI index falls"), keep strategy_type
  SINGLE_STOCK with universe symbols containing only the traded stock, and set the `symbol`
  field on the relevant IndicatorReference (left or right operand) to the signal symbol
  (for example KOSPI index ticker). Do not silently evaluate the condition against the
  traded stock's own data when the user named a different signal asset.
- For a two-asset full-allocation switch such as "when SPY is below SMA 30, hold GLD",
  return strategy_type REGIME_SWITCH with exactly two symbols, default_symbol, and switch_rule.
- For a fixed multi-asset allocation request such as "hold SPY 60% and GLD 40%, rebalanced monthly",
  return strategy_type ALLOCATION_REBALANCE with 2 to 5 symbols, target_allocations whose weights
  sum to 1 or less, and a rebalance frequency. Unallocated weight remains cash.
- Rebalance frequency must be one of WEEKLY, MONTHLY, or QUARTERLY. Map "weekly"/"주간"/"매주" to
  WEEKLY, "monthly"/"월간"/"매월" to MONTHLY, and "quarterly"/"분기"/"분기별" to QUARTERLY.
  Default to MONTHLY only when the user does not specify a rebalancing cadence.
- ALLOCATION_REBALANCE also supports rebalance.weight_tolerance (skip trading a symbol whose
  weight is already within this fraction of its target, for example "리밸런싱은 5%p 이상 벗어날 때만"
  → 0.05), rebalance.min_order_lot (round order sizes down to a whole multiple of this many
  shares), and rebalance.rebalance_cost (a fixed fee charged once per rebalance event that
  actually trades, distinct from per-trade commission/slippage/tax). Leave these at their
  defaults (0, 1, 0) unless the user specifies them.
- ALLOCATION_REBALANCE also supports conditional_target_allocations: a list of
  {condition, target_allocations} rules checked in order, where the base target_allocations is
  the fallback when no rule matches. Use this for requests like "지수가 SMA 200 아래로 떨어지면
  현금 비중을 늘려라" (switch to a more defensive weight set when a condition is true). A
  condition's IndicatorReference may set `symbol` to any universe symbol; omit `symbol` to mean
  the first universe symbol.
- A single-stock condition's signal symbol is not limited to other stocks or indices --
  macro series (FX rates, interest rates, commodity futures, volatility) are valid signal
  symbols too, using their Yahoo Finance ticker via the same IndicatorReference.symbol
  mechanism. Map common Korean phrases to these tickers:
  원/달러 환율 or USD/KRW → KRW=X · 미국 10년물 금리 or US 10-year yield → ^TNX ·
  국제유가 or WTI → CL=F · 국제 금 시세 or gold → GC=F · VIX or 변동성지수 → ^VIX ·
  나스닥 or NASDAQ → ^IXIC · S&P500 → ^GSPC · 필라델피아 반도체지수 or SOX → ^SOX ·
  코스피 → ^KS11 · 코스닥 → ^KQ11. These tickers only exist on Yahoo Finance, never on
  pykrx, regardless of the traded stock's market.
- Calendar and price-pattern indicators are available for conditions that don't need any
  external data: DAY_OF_WEEK (Monday=0..Friday=4, compare with EQUAL to a VALUE — "월요일"→0,
  "금요일"→4), MONTH_OF_YEAR (1-12), CONSECUTIVE_UP_DAYS / CONSECUTIVE_DOWN_DAYS (compare with
  GREATER_THAN_OR_EQUAL to an integer count — "3일 연속 상승"→CONSECUTIVE_UP_DAYS >= 3),
  GAP_RETURN (today's open vs yesterday's close as a fraction, e.g. -0.05 for a 5% gap down),
  N_WEEK_HIGH / N_WEEK_LOW (period is in weeks, e.g. 52 for "52주 신고가"). None of these need
  a `symbol` unless the user is asking about a different asset's calendar/pattern than the
  traded one.
- Do not rewrite an unsupported multi-asset, portfolio, or allocation request as a cash or
  single-stock strategy. Instead, return the closest safe draft only when representable and
  clearly add the unsupported intent to warnings and missing_fields.
- If the request cannot be represented by the schema, explain it in warnings and use no unsupported feature.
"""

EXPLANATION_SYSTEM_PROMPT = """You explain fixed backtest results in Korean.

Rules:
- Use only the supplied values. Do not calculate, change, infer, or fabricate metrics.
- Use the supplied human-readable formatted values exactly. Never output raw floating-point values.
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
        configured_api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        # Environment-variable UIs can accidentally retain a trailing newline.
        self.api_key = configured_api_key.strip() if configured_api_key else None
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
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
            # Never log request headers or exception details because they can include API keys.
            logger.warning("OpenAI strategy parsing failed: %s", type(error).__name__)
            raise OpenAIClientError(
                f"OpenAI strategy parsing failed ({type(error).__name__})"
            ) from error
        if response.output_parsed is None:
            raise OpenAIClientError("OpenAI returned no structured strategy")
        return response.output_parsed

    def explain_backtest(self, result: BacktestResponse) -> BacktestExplanation:
        if not self.api_key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        payload = {
            "data_period": f"{result.data_start_date} ~ {result.data_end_date}",
            "data_points": result.data_points,
            "total_return": _format_percent(result.total_return),
            "cagr": _format_percent(result.cagr),
            "max_drawdown": _format_percent(result.max_drawdown),
            "volatility": _format_percent(result.volatility),
            "sharpe_ratio": f"{result.sharpe_ratio:.2f}",
            "win_rate": _format_percent(result.win_rate),
            "trade_count": result.trade_count,
            "average_holding_days": f"{result.average_holding_days:.1f}일",
            "total_cost": f"{result.total_cost:,.0f} KRW",
            "benchmark_name": result.benchmark_name,
            "benchmark_total_return": _format_percent(result.benchmark_total_return),
            "benchmark_max_drawdown": _format_percent(result.benchmark_max_drawdown),
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
            logger.warning("OpenAI backtest explanation failed: %s", type(error).__name__)
            raise OpenAIClientError(
                f"OpenAI backtest explanation failed ({type(error).__name__})"
            ) from error
        if response.output_parsed is None:
            raise OpenAIClientError("OpenAI returned no structured explanation")
        return response.output_parsed


def _format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"
