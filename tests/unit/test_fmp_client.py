from datetime import date

import httpx
import pytest

from services.api.app.clients.fmp_client import FMPClient, FMPClientError


class FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_fmp_client_normalizes_and_adjusts_daily_ohlcv(monkeypatch):
    def fake_get(url, params, headers, timeout):
        assert url.endswith("/historical-price-eod/dividend-adjusted")
        assert params == {"symbol": "NVDA"}
        assert headers == {"apikey": "test-key"}
        assert timeout == 20.0
        return FakeResponse(200, [
            {"date": "2024-01-03", "adjOpen": 51, "adjHigh": 52, "adjLow": 50.5, "adjClose": 51, "volume": 300},
            {"date": "2024-01-02", "adjOpen": 50, "adjHigh": 51, "adjLow": 49.5, "adjClose": 50, "volume": 200},
        ])

    monkeypatch.setattr(httpx, "get", fake_get)
    data, adjustment = FMPClient(api_key="test-key").fetch_daily_ohlcv(
        "nvda", date(2024, 1, 2), date(2024, 1, 3), adjusted_price=True
    )

    assert list(data.index.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]
    assert data.loc["2024-01-02", "open"] == 50
    assert data.loc["2024-01-03", "close"] == 51
    assert adjustment == "FMP dividend-adjusted EOD OHLCV"


def test_fmp_client_reports_missing_key():
    with pytest.raises(FMPClientError, match="FMP_API_KEY"):
        FMPClient(api_key="").fetch_daily_ohlcv(
            "AAPL", date(2024, 1, 1), date(2024, 1, 2), adjusted_price=False
        )


def test_fmp_client_reports_rate_limit(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *_, **__: FakeResponse(429, []))
    with pytest.raises(FMPClientError, match="rate limit"):
        FMPClient(api_key="test-key").fetch_daily_ohlcv(
            "AAPL", date(2024, 1, 1), date(2024, 1, 2), adjusted_price=False
        )
