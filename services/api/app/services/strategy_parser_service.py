from ..clients.openai_client import OpenAIStrategyClient
from ..schemas.strategy_parse_schema import StrategyParseResult
from ..schemas.strategy_schema import AllocationRebalanceStrategy, RegimeSwitchStrategy


class StrategyParserService:
    def __init__(self, client: OpenAIStrategyClient | None = None) -> None:
        self.client = client or OpenAIStrategyClient()

    def parse(self, raw_input: str) -> StrategyParseResult:
        result = self.client.parse_strategy(raw_input)
        # This is a safety invariant even if a future client implementation changes.
        result.needs_confirmation = True
        if _requests_asset_switch(raw_input) and not isinstance(result.strategy, RegimeSwitchStrategy):
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
        return result


def _requests_asset_switch(raw_input: str) -> bool:
    text = raw_input.lower()
    return any(keyword in text for keyword in ("전환", "갈아타", "대신", "switch", "rotate", "rotation"))


def _requests_allocation(raw_input: str) -> bool:
    text = raw_input.lower()
    return any(keyword in text for keyword in ("비중", "배분", "리밸런싱", "rebalance", "allocation"))
