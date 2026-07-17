from datetime import date, timedelta

import pandas as pd

from ..backtest_engine.market_data import validate_ohlcv


class YFinanceClientError(RuntimeError):
    """Raised when Yahoo Finance cannot provide usable daily OHLCV data."""


class YFinanceClient:
    def search_symbols(self, query: str, limit: int = 8) -> list[tuple[str, str]]:
        try:
            import yfinance as yf
        except ImportError as error:
            raise YFinanceClientError(
                "yfinance is not installed; install the market-data dependencies"
            ) from error
        try:
            quotes = yf.Search(query, max_results=limit).quotes
        except Exception as error:
            raise YFinanceClientError("Yahoo Finance symbol search failed") from error

        results: list[tuple[str, str]] = []
        for quote in quotes or []:
            symbol = quote.get("symbol") if isinstance(quote, dict) else None
            if not symbol:
                continue
            name = quote.get("shortname") or quote.get("longname") or symbol
            results.append((str(symbol).upper(), str(name)))
        return results[:limit]

    def fetch_daily_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjusted_price: bool,
    ) -> tuple[pd.DataFrame, str]:
        if start_date > end_date:
            raise YFinanceClientError("start_date must not be after end_date")
        try:
            import yfinance as yf
        except ImportError as error:
            raise YFinanceClientError(
                "yfinance is not installed; install the market-data dependencies"
            ) from error

        try:
            data = yf.download(
                symbol.upper(),
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                interval="1d",
                auto_adjust=adjusted_price,
                actions=False,
                progress=False,
                threads=False,
                multi_level_index=False,
            )
        except Exception as error:  # yfinance exposes several transport exceptions.
            raise YFinanceClientError("Yahoo Finance request failed") from error

        if not isinstance(data, pd.DataFrame) or data.empty:
            raise YFinanceClientError(f"Yahoo Finance returned no daily data for {symbol.upper()}")
        required = {"Open", "High", "Low", "Close", "Volume"}
        if isinstance(data.columns, pd.MultiIndex):
            # yfinance versions differ: either (Price, Ticker) or (Ticker, Price).
            ohlcv_level = next(
                (
                    level
                    for level in range(data.columns.nlevels)
                    if required.issubset(set(data.columns.get_level_values(level)))
                ),
                None,
            )
            if ohlcv_level is None:
                raise YFinanceClientError("Yahoo Finance response does not contain complete daily OHLCV data")
            ticker_level = 1 - ohlcv_level if data.columns.nlevels == 2 else None
            if ticker_level is not None and len(data.columns.get_level_values(ticker_level).unique()) != 1:
                raise YFinanceClientError("Yahoo Finance returned multiple tickers for a single-symbol request")
            data.columns = data.columns.get_level_values(ohlcv_level)
        if not required.issubset(data.columns):
            raise YFinanceClientError("Yahoo Finance response does not contain complete daily OHLCV data")
        data = data[["Open", "High", "Low", "Close", "Volume"]]
        data = data.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume",
        })
        if data.columns.duplicated().any():
            raise YFinanceClientError("Yahoo Finance response contains duplicate OHLCV columns")
        data.index = pd.to_datetime(data.index, errors="raise").tz_localize(None)
        data.index.name = "date"
        data = data.loc[(data.index.date >= start_date) & (data.index.date <= end_date)]
        if data.empty:
            raise YFinanceClientError("Yahoo Finance returned no market data within the requested date range")

        adjustment = (
            "Yahoo Finance auto-adjusted daily OHLCV"
            if adjusted_price
            else "Yahoo Finance unadjusted daily OHLCV"
        )
        return validate_ohlcv(data[["open", "high", "low", "close", "volume"]]), adjustment
