from fastapi import APIRouter, HTTPException

from ..clients.openai_client import OpenAIClientError
from ..schemas.strategy_parse_schema import StrategyParseRequest, StrategyParseResult
from ..services.strategy_parser_service import StrategyParserService

router = APIRouter(prefix="/api/v1/strategy-drafts", tags=["strategy-drafts"])
parser_service = StrategyParserService()


@router.post("/parse", response_model=StrategyParseResult)
def parse_strategy(request: StrategyParseRequest) -> StrategyParseResult:
    try:
        return parser_service.parse(request.raw_input)
    except OpenAIClientError as error:
        status_code = 503 if "not configured" in str(error) else 502
        raise HTTPException(status_code=status_code, detail=str(error)) from error
