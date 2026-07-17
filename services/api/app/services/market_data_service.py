from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path

import pandas as pd

from ..backtest_engine.market_data import DataVersion, build_data_version
from ..clients.fmp_client import FMPClient, FMPClientError
from ..clients.pykrx_client import PykrxClient, PykrxClientError
from ..clients.yfinance_client import YFinanceClient, YFinanceClientError


@dataclass(frozen=True)
class MarketDataFetch:
    provider: str
    symbol: str
    adjustment: str
    data: pd.DataFrame
    data_version: DataVersion
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MarketSymbol:
    provider: str
    symbol: str
    name: str


class MarketDataService:
    """Fetch and retain normalized daily data so a result can be reproduced."""

    def fetch(
        self,
        provider: str,
        symbol: str,
        start_date: date,
        end_date: date,
        adjusted_price: bool,
    ) -> MarketDataFetch:
        provider = provider.upper()
        if provider not in {"YFINANCE", "PYKRX", "FMP"}:
            raise ValueError(f"unsupported market data provider: {provider}")

        try:
            if provider == "YFINANCE":
                data, adjustment = YFinanceClient().fetch_daily_ohlcv(
                    symbol, start_date, end_date, adjusted_price
                )
            elif provider == "PYKRX":
                data, adjustment = PykrxClient().fetch_daily_ohlcv(
                    symbol, start_date, end_date, adjusted_price
                )
            else:
                data, adjustment = FMPClient().fetch_daily_ohlcv(
                    symbol, start_date, end_date, adjusted_price
                )
        except (FMPClientError, PykrxClientError, YFinanceClientError) as error:
            raise ValueError(str(error)) from error

        data_version = build_data_version(data)
        collected_at = datetime.now(timezone.utc)
        self._cache(provider, symbol, data, data_version, adjustment, collected_at)
        return MarketDataFetch(
            provider=provider,
            symbol=symbol.upper(),
            adjustment=adjustment,
            data=data,
            data_version=data_version,
            collected_at=collected_at,
        )

    def search_symbols(self, provider: str, query: str, limit: int = 8) -> list[MarketSymbol]:
        provider = provider.upper()
        query = query.strip()
        if provider not in {"YFINANCE", "PYKRX"}:
            raise ValueError(f"symbol search is not supported for provider: {provider}")
        if not query:
            raise ValueError("search query must not be empty")
        try:
            pairs = (
                YFinanceClient().search_symbols(query, limit)
                if provider == "YFINANCE"
                else PykrxClient().search_symbols(query, limit)
            )
        except (PykrxClientError, YFinanceClientError) as error:
            raise ValueError(str(error)) from error
        return [MarketSymbol(provider=provider, symbol=symbol, name=name) for symbol, name in pairs]

    @staticmethod
    def _cache(
        provider: str,
        symbol: str,
        data: pd.DataFrame,
        version: DataVersion,
        adjustment: str,
        collected_at: datetime,
    ) -> None:
        # The hash is part of the filename: later requests never overwrite prior input data.
        directory = (
            Path(os.getenv("ALPHALENS_MARKET_DATA_PATH", "data/market_data"))
            / provider.lower()
            / symbol.upper()
        )
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{version.identifier.removeprefix('sha256:')}.csv"
        if not path.exists():
            data.to_csv(path, index_label="date")
        metadata_path = path.with_suffix(".json")
        if not metadata_path.exists():
            metadata_path.write_text(json.dumps({
                "provider": provider,
                "symbol": symbol.upper(),
                "adjustment": adjustment,
                "data_version": version.identifier,
                "data_start_date": version.start_date,
                "data_end_date": version.end_date,
                "data_points": version.point_count,
                "collected_at": collected_at.isoformat(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")


market_data_service = MarketDataService()
