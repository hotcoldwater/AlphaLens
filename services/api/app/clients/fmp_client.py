import os
from datetime import date
from typing import Any

import httpx
import pandas as pd

from ..backtest_engine.market_data import validate_ohlcv


class FMPClientError(RuntimeError):
    """Raised when FMP cannot provide usable daily OHLCV data."""


class FMPClient:
    base_url = "https://financialmodelingprep.com/stable"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("FMP_API_KEY")

    def fetch_daily_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjusted_price: bool,
    ) -> tuple[pd.DataFrame, str]:
        if not self.api_key:
            raise FMPClientError("FMP_API_KEY is not configured")
        if start_date > end_date:
            raise FMPClientError("start_date must not be after end_date")

        try:
            endpoint = (
                "historical-price-eod/dividend-adjusted"
                if adjusted_price
                else "historical-price-eod/full"
            )
            response = httpx.get(
                f"{self.base_url}/{endpoint}",
                params={"symbol": symbol.upper()},
                headers={"apikey": self.api_key},
                timeout=20.0,
            )
        except httpx.HTTPError as error:
            raise FMPClientError("FMP request failed") from error

        if response.status_code == 403:
            raise FMPClientError("FMP API key is invalid or does not have access to this endpoint")
        if response.status_code == 429:
            raise FMPClientError("FMP API rate limit exceeded; try again later")
        if response.status_code >= 400:
            raise FMPClientError(f"FMP request failed with status {response.status_code}")

        payload: Any = response.json()
        if not isinstance(payload, list):
            message = payload.get("Error Message") if isinstance(payload, dict) else None
            raise FMPClientError(message or "FMP returned an unexpected response")
        if not payload:
            raise FMPClientError(f"FMP returned no daily data for {symbol.upper()}")

        data = pd.DataFrame(payload)
        required = (
            {"date", "adjOpen", "adjHigh", "adjLow", "adjClose", "volume"}
            if adjusted_price
            else {"date", "open", "high", "low", "close", "volume"}
        )
        if not required.issubset(data.columns):
            raise FMPClientError("FMP response does not contain complete daily OHLCV data")
        if adjusted_price:
            data = data.rename(columns={
                "adjOpen": "open",
                "adjHigh": "high",
                "adjLow": "low",
                "adjClose": "close",
            })
        data["date"] = pd.to_datetime(data["date"], errors="raise")
        data = data.set_index("date").sort_index()
        data = data.loc[(data.index.date >= start_date) & (data.index.date <= end_date)]
        if data.empty:
            raise FMPClientError("FMP returned no market data within the requested date range")

        adjustment = (
            "FMP dividend-adjusted EOD OHLCV"
            if adjusted_price
            else "FMP unadjusted EOD OHLCV"
        )

        return validate_ohlcv(data[["open", "high", "low", "close", "volume"]]), adjustment
