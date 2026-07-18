from datetime import date

import pandas as pd

from ..backtest_engine.market_data import validate_ohlcv


class PykrxClientError(RuntimeError):
    """Raised when pykrx cannot provide usable KRX daily OHLCV data."""


class PykrxClient:
    def search_symbols(self, query: str, limit: int = 8) -> list[tuple[str, str]]:
        try:
            from pykrx import stock
        except ImportError as error:
            raise PykrxClientError(
                "pykrx is not installed; install the market-data dependencies"
            ) from error
        try:
            tickers = stock.get_market_ticker_list(market="ALL")
            normalized_query = query.strip().upper()
            matches: list[tuple[str, str]] = []
            for ticker in tickers:
                name = stock.get_market_ticker_name(ticker)
                if normalized_query in ticker or normalized_query in name.upper():
                    matches.append((ticker, name))
                    if len(matches) == limit:
                        break
            return matches
        except Exception as error:
            raise PykrxClientError("pykrx symbol search failed") from error

    def fetch_daily_ohlcv(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjusted_price: bool,
    ) -> tuple[pd.DataFrame, str]:
        if start_date > end_date:
            raise PykrxClientError("start_date must not be after end_date")
        try:
            from pykrx import stock
        except ImportError as error:
            raise PykrxClientError(
                "pykrx is not installed; install the market-data dependencies"
            ) from error

        try:
            data = stock.get_market_ohlcv_by_date(
                start_date.strftime("%Y%m%d"),
                end_date.strftime("%Y%m%d"),
                symbol.strip(),
                adjusted=adjusted_price,
            )
        except Exception as error:  # pykrx wraps KRX and Naver transport errors.
            raise PykrxClientError("pykrx request failed") from error

        if data is None or data.empty:
            raise PykrxClientError(
                f"pykrx returned no daily data for {symbol.strip()}. "
                "Check the six-digit KRX ticker and requested period; the security may be delisted, halted, or unavailable."
            )
        required = {"시가", "고가", "저가", "종가", "거래량"}
        if not required.issubset(data.columns):
            raise PykrxClientError("pykrx response does not contain complete daily OHLCV data")

        data = data.rename(columns={
            "시가": "open", "고가": "high", "저가": "low", "종가": "close", "거래량": "volume",
        })
        data.index = pd.to_datetime(data.index, errors="raise")
        data.index.name = "date"
        data = data.loc[(data.index.date >= start_date) & (data.index.date <= end_date)]
        # Around corporate actions (e.g. a stock split), pykrx sometimes reports a
        # placeholder row with open/high/low all zero and only close carried
        # forward, for a session the security didn't actually trade in. These
        # aren't real trading days, so drop them instead of failing the whole
        # fetch on an OHLC-positivity check.
        data = data[data["open"] > 0]
        if data.empty:
            raise PykrxClientError(
                "pykrx returned no market data within the requested date range. "
                "The security may not have been listed or tradable during that period."
            )

        adjustment = (
            "pykrx adjusted daily OHLCV"
            if adjusted_price
            else "pykrx unadjusted daily OHLCV"
        )
        return validate_ohlcv(data[["open", "high", "low", "close", "volume"]]), adjustment
