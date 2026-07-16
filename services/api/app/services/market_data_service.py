from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from ..backtest_engine.market_data import DataVersion, build_data_version
from ..clients.fmp_client import FMPClient, FMPClientError


@dataclass(frozen=True)
class MarketDataFetch:
    provider: str
    symbol: str
    adjustment: str
    data: pd.DataFrame
    data_version: DataVersion


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
        if provider == "KRX":
            raise ValueError(
                "KRX Open API integration is pending approval. Set KRX_API_KEY after approval, then enable the requested KRX service."
            )
        if provider != "FMP":
            raise ValueError(f"unsupported market data provider: {provider}")

        try:
            data, adjustment = FMPClient().fetch_daily_ohlcv(
                symbol, start_date, end_date, adjusted_price
            )
        except FMPClientError as error:
            raise ValueError(str(error)) from error

        data_version = build_data_version(data)
        self._cache(provider, symbol, data, data_version)
        return MarketDataFetch(
            provider=provider,
            symbol=symbol.upper(),
            adjustment=adjustment,
            data=data,
            data_version=data_version,
        )

    @staticmethod
    def _cache(provider: str, symbol: str, data: pd.DataFrame, version: DataVersion) -> None:
        # The hash is part of the filename: later requests never overwrite prior input data.
        directory = Path("data/market_data") / provider.lower() / symbol.upper()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{version.identifier.removeprefix('sha256:')}.csv"
        if not path.exists():
            data.to_csv(path, index_label="date")


market_data_service = MarketDataService()
