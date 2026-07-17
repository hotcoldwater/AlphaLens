from datetime import date
import sys
from types import ModuleType

import pandas as pd
import pytest

from services.api.app.clients.pykrx_client import PykrxClientError
from services.api.app.clients.pykrx_client import PykrxClient
from services.api.app.clients.yfinance_client import YFinanceClientError
from services.api.app.clients.yfinance_client import YFinanceClient
from services.api.app.services import market_data_service as market_data_module


def sample_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000.0, 1100.0],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )


def test_yfinance_client_normalizes_download(monkeypatch):
    module = ModuleType("yfinance")

    def download(symbol, **kwargs):
        assert symbol == "NVDA"
        assert kwargs["auto_adjust"] is True
        assert kwargs["end"] == "2024-01-04"
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0], "High": [102.0, 103.0],
                "Low": [99.0, 100.0], "Close": [101.0, 102.0], "Volume": [1000, 1100],
            },
            index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
        )

    module.download = download
    monkeypatch.setitem(sys.modules, "yfinance", module)

    data, adjustment = YFinanceClient().fetch_daily_ohlcv(
        "nvda", date(2024, 1, 2), date(2024, 1, 3), True
    )

    assert list(data.columns) == ["open", "high", "low", "close", "volume"]
    assert list(data.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert adjustment == "Yahoo Finance auto-adjusted daily OHLCV"


def test_yfinance_client_flattens_single_ticker_multiindex_columns(monkeypatch):
    module = ModuleType("yfinance")

    def download(*args, **kwargs):
        return pd.DataFrame(
            [[100.0, 102.0, 99.0, 101.0, 1000]],
            columns=pd.MultiIndex.from_tuples([
                ("Open", "TSLA"), ("High", "TSLA"), ("Low", "TSLA"),
                ("Close", "TSLA"), ("Volume", "TSLA"),
            ]),
            index=pd.to_datetime(["2024-01-02"]),
        )

    module.download = download
    monkeypatch.setitem(sys.modules, "yfinance", module)

    data, _ = YFinanceClient().fetch_daily_ohlcv(
        "TSLA", date(2024, 1, 2), date(2024, 1, 2), True
    )

    assert data.loc["2024-01-02", "close"] == 101


def test_yfinance_client_flattens_ticker_first_multiindex_columns(monkeypatch):
    module = ModuleType("yfinance")

    def download(*args, **kwargs):
        return pd.DataFrame(
            [[100.0, 102.0, 99.0, 101.0, 1000]],
            columns=pd.MultiIndex.from_tuples([
                ("GLD", "Open"), ("GLD", "High"), ("GLD", "Low"),
                ("GLD", "Close"), ("GLD", "Volume"),
            ]),
            index=pd.to_datetime(["2024-01-02"]),
        )

    module.download = download
    monkeypatch.setitem(sys.modules, "yfinance", module)

    data, _ = YFinanceClient().fetch_daily_ohlcv(
        "GLD", date(2024, 1, 2), date(2024, 1, 2), True
    )

    assert data.loc["2024-01-02", "close"] == 101


def test_pykrx_client_normalizes_download(monkeypatch):
    module = ModuleType("pykrx")

    class Stock:
        @staticmethod
        def get_market_ohlcv_by_date(start, end, ticker, **kwargs):
            assert (start, end, ticker, kwargs) == ("20240102", "20240103", "005930", {"adjusted": False})
            return pd.DataFrame(
                {
                    "시가": [70000.0, 71000.0], "고가": [71000.0, 72000.0],
                    "저가": [69000.0, 70000.0], "종가": [70500.0, 71500.0], "거래량": [1000, 1100],
                },
                index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
            )

    module.stock = Stock
    monkeypatch.setitem(sys.modules, "pykrx", module)

    data, adjustment = PykrxClient().fetch_daily_ohlcv(
        "005930", date(2024, 1, 2), date(2024, 1, 3), False
    )

    assert data.loc["2024-01-03", "close"] == 71500
    assert adjustment == "pykrx unadjusted daily OHLCV"


@pytest.mark.parametrize(
    ("provider", "client_name", "symbol", "adjustment"),
    [
        ("YFINANCE", "YFinanceClient", "NVDA", "Yahoo Finance auto-adjusted daily OHLCV"),
        ("PYKRX", "PykrxClient", "005930", "pykrx adjusted daily OHLCV"),
    ],
)
def test_market_data_service_fetches_personal_provider(
    monkeypatch, tmp_path, provider, client_name, symbol, adjustment
):
    class FakeClient:
        def fetch_daily_ohlcv(self, *args, **kwargs):
            return sample_data(), adjustment

    monkeypatch.setattr(market_data_module, client_name, FakeClient)
    monkeypatch.setenv("ALPHALENS_MARKET_DATA_PATH", str(tmp_path))

    result = market_data_module.MarketDataService().fetch(
        provider, symbol, date(2024, 1, 1), date(2024, 1, 31), True
    )

    assert result.provider == provider
    assert result.symbol == symbol
    assert result.adjustment == adjustment
    assert result.data_version.point_count == 2
    assert list((tmp_path / provider.lower() / symbol).glob("*.csv"))


@pytest.mark.parametrize(
    ("provider", "error"),
    [
        ("YFINANCE", YFinanceClientError("unavailable")),
        ("PYKRX", PykrxClientError("unavailable")),
    ],
)
def test_market_data_service_translates_personal_provider_errors(monkeypatch, provider, error):
    class FakeClient:
        def fetch_daily_ohlcv(self, *args, **kwargs):
            raise error

    monkeypatch.setattr(
        market_data_module,
        "YFinanceClient" if provider == "YFINANCE" else "PykrxClient",
        FakeClient,
    )

    with pytest.raises(ValueError, match="unavailable"):
        market_data_module.MarketDataService().fetch(
            provider, "NVDA", date(2024, 1, 1), date(2024, 1, 31), True
        )
