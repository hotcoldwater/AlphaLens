from ..clients.openai_client import OpenAIStrategyClient
from ..schemas.strategy_parse_schema import StrategyParseResult
from ..schemas.strategy_schema import (
    AllocationRebalanceStrategy,
    RegimeSwitchStrategy,
    StrategyDefinition,
)


class StrategyParserService:
    def __init__(self, client: OpenAIStrategyClient | None = None) -> None:
        self.client = client or OpenAIStrategyClient()

    def parse(self, raw_input: str) -> StrategyParseResult:
        result = self.client.parse_strategy(raw_input)
        # This is a safety invariant even if a future client implementation changes.
        result.needs_confirmation = True
        # The model may conservatively set this flag even when it returned a fully
        # valid multi-asset schema. A validated executable strategy must not be
        # blocked by that advisory model flag.
        if isinstance(result.strategy, (RegimeSwitchStrategy, AllocationRebalanceStrategy)):
            result.needs_clarification = False
        if _requests_asset_switch(raw_input) and not isinstance(
            result.strategy, (RegimeSwitchStrategy, AllocationRebalanceStrategy)
        ):
            result.needs_clarification = True
            result.warnings.append(
                "요청에 여러 자산 간 전환 의도가 있지만 실행 가능한 자산 전환 전략으로 해석되지 않았습니다. 현금 보유 전략으로 자동 변경하지 않습니다."
            )
            result.missing_fields.append("전환 대상 자산과 조건을 다시 확인")
        if _requests_allocation(raw_input) and not isinstance(result.strategy, AllocationRebalanceStrategy):
            result.needs_clarification = True
            result.warnings.append(
                "요청에 다중 자산 비중 배분 또는 리밸런싱 의도가 있지만 실행 가능한 배분 전략으로 해석되지 않았습니다. 단일 종목 전략으로 자동 변경하지 않습니다."
            )
            result.missing_fields.append("자산별 목표 비중과 리밸런싱 주기를 다시 확인")
        if requires_external_signal_support(raw_input, result.strategy):
            result.needs_clarification = True
            result.warnings.append(
                "요청에 KOSPI·KOSDAQ 등 별도 지수를 신호로 쓰려는 의도가 있지만, 신호 종목이 "
                "주문 종목과 분리되어 해석되지 않았습니다. 조건의 신호 종목을 다시 확인하세요."
            )
            result.missing_fields.append("신호 종목과 주문 종목을 분리하는 조건 확인")
        return result


def _requests_asset_switch(raw_input: str) -> bool:
    text = raw_input.lower()
    return any(keyword in text for keyword in ("전환", "갈아타", "대신", "switch", "rotate", "rotation"))


def _requests_allocation(raw_input: str) -> bool:
    text = raw_input.lower()
    return any(keyword in text for keyword in ("비중", "배분", "리밸런싱", "rebalance", "allocation"))


def requires_external_signal_support(
    raw_input: str, strategy: StrategyDefinition,
) -> bool:
    """Return True when the request implies an index signal but the parsed
    strategy's conditions do not actually reference a separate signal symbol.

    The single-stock engine can evaluate a condition against a different
    symbol's OHLCV via IndicatorReference.symbol (see Strategy.signal_symbols()).
    If the model mentions an index but failed to set that field, the condition
    would silently fall back to the traded symbol's own data, so this must be
    flagged for user confirmation instead of executed as-is.
    """
    if isinstance(strategy, (RegimeSwitchStrategy, AllocationRebalanceStrategy)):
        return False
    if strategy.signal_symbols():
        return False
    text = raw_input.lower()
    index_reference = any(
        keyword in text
        for keyword in ("kospi", "코스피", "kosdaq", "코스닥", "s&p", "sp500", "다우", "나스닥 지수")
    )
    signal_reference = any(
        keyword in text
        for keyword in ("수익률", "상승", "하락", "양봉", "음봉", "return", "signal", "신호")
    )
    return index_reference and signal_reference
