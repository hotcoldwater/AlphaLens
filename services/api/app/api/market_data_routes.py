from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from ..schemas.backtest_schema import (
    MarketDataFetchRequest,
    MarketDataFetchResponse,
    MarketSymbolResponse,
    OHLCVBar,
)
from ..services.market_data_service import market_data_service

router = APIRouter(prefix="/api/v1/market-data", tags=["market-data"])


@router.get("/symbols/search", response_model=list[MarketSymbolResponse])
def search_symbols(
    provider: Literal["YFINANCE", "PYKRX"] = Query(),
    query: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=8, ge=1, le=20),
) -> list[MarketSymbolResponse]:
    try:
        symbols = market_data_service.search_symbols(provider, query, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return [MarketSymbolResponse(**symbol.__dict__) for symbol in symbols]


@router.post("/daily-ohlcv", response_model=MarketDataFetchResponse)
def fetch_daily_ohlcv(request: MarketDataFetchRequest) -> MarketDataFetchResponse:
    try:
        result = market_data_service.fetch(
            provider=request.provider,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            adjusted_price=request.adjusted_price,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return MarketDataFetchResponse(
        provider=result.provider,
        symbol=result.symbol,
        adjustment=result.adjustment,
        data_version=result.data_version.identifier,
        data_start_date=result.data_version.start_date,
        data_end_date=result.data_version.end_date,
        data_points=result.data_version.point_count,
        collected_at=result.collected_at,
        data=[
            OHLCVBar(
                date=index.date(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for index, row in result.data.iterrows()
        ],
    )
