from datetime import datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from core.errors import AppError
from services.candle_service import CandleSeries, CandleService
from services.position_timing import choose_interval, compute_timing, local_to_utc, split_time
from services.providers.base import Candle, ProviderError
from tests.conftest import login
from tests.test_portfolios_api import add_position, create_portfolio, positions_of, sell

H = 3600


def candle(t, close):
    c = D(close)
    return Candle(t, c, c, c, c, D(1))


def test_split_time_by_candle_close():
    candles = [candle(0, "90"), candle(H, "110"), candle(2 * H, "99"), candle(3 * H, "100")]
    # position from 0:30 to 3:15, entry 100: below = 0.5h + 1h, above = 1h + 0.25h
    split = split_time(candles, H, 1800, 3 * H + 900, D("100"))
    assert (split.below_seconds, split.above_seconds, split.unknown_seconds) == (5400, 4500, 0)
    # missing candles -> unknown
    assert split_time([candle(0, "90")], H, 0, 2 * H, D("100")).unknown_seconds == H


def test_interval_and_timezone():
    assert choose_interval(10 * 60) == "1m"
    assert choose_interval(3 * 86400) == "5m"
    assert choose_interval(400 * 86400) == "1d"
    # Europe/Warsaw: UTC+2 in summer, UTC+1 in winter
    assert local_to_utc(datetime(2026, 7, 1, 12, 0), "Europe/Warsaw").hour == 10
    assert local_to_utc(datetime(2026, 1, 1, 12, 0), "Europe/Warsaw").hour == 11


class FakeCandles:
    def __init__(self, closes_by_hour):
        self.closes = closes_by_hour
        self.calls = []

    def get_candles(self, symbol, interval, start, end, max_candles=5000):
        self.calls.append((symbol, interval, start, end))
        step = {"1m": 60, "5m": 300, "15m": 900, "1h": H}[interval]
        first = start // step * step
        candles = [candle(t, self.closes[(t - first) // H % len(self.closes)]) for t in range(first, end, step)]
        return CandleSeries(symbol, interval, "fake", candles)


def make_position(sales=(), quantity="1"):
    return SimpleNamespace(id=1, symbol="BTC", buy_price=D("100"), quantity=D(quantity), fee_coin=D(0),
                           bought_at=datetime(2026, 1, 1, 13, 0), sales=list(sales))


def test_closed_position_ends_at_last_sale():
    sales = [SimpleNamespace(id=1, quantity=D("0.4"), sold_at=datetime(2026, 1, 1, 14, 0)),
             SimpleNamespace(id=2, quantity=D("0.6"), sold_at=datetime(2026, 1, 1, 16, 0))]
    timing = compute_timing(make_position(sales), FakeCandles(["90", "120", "95"]), "Europe/Warsaw",
                            now=datetime(2026, 1, 5, tzinfo=timezone.utc))
    assert timing.is_open is False
    assert timing.start == datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert timing.duration_seconds == 3 * H                       # until the LAST sale
    assert timing.below_seconds == 2 * H and timing.above_seconds == H
    assert timing.below_pct == D("66.67")
    assert timing.interval == "1m"                                # 180 one-minute candles


def test_partially_sold_position_is_still_open():
    sales = [SimpleNamespace(id=1, quantity=D("0.4"), sold_at=datetime(2026, 1, 1, 14, 0))]
    now = datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc)       # 2 h after purchase (13:00 local = 12:00 UTC)
    timing = compute_timing(make_position(sales), FakeCandles(["120"]), "Europe/Warsaw", now=now)
    assert timing.is_open is True
    assert timing.end == now and timing.duration_seconds == 2 * H
    assert timing.above_seconds == 2 * H and timing.below_pct == D("0.00")


def test_timing_endpoint(client, monkeypatch):
    import api.routes.portfolios as routes
    fake = FakeCandles(["90", "110"])
    monkeypatch.setattr(routes, "candle_service", fake)
    headers = login(client)
    portfolio = create_portfolio(client, headers)
    view = add_position(client, headers, portfolio["id"], buy_price="100", fee_coin="0", bought_at="2026-01-01T13:00")
    position_id = positions_of(view)[0]["id"]
    sell(client, headers, portfolio["id"], [(position_id, "1")], sold_at="2026-01-01T15:00")

    body = client.get(f"/api/positions/{position_id}/timing", headers=headers).json()
    assert body["is_open"] is False and body["duration_seconds"] == 2 * H
    assert (body["below_seconds"], body["above_seconds"]) == (H, H)

    client.get(f"/api/positions/{position_id}/timing", headers=headers)
    assert len(fake.calls) == 1                                    # closed position -> cached


# ------------------------------------------------------------------ candle service

class FakePrices:
    quote_currency = "USDT"

    def __init__(self, sources):
        self.sources = sources

    def sources_for(self, symbol):
        return self.sources


def test_candle_service_fallback_and_cache():
    calls = []

    def failing(*args):
        calls.append("bybit")
        raise ProviderError("connection_error", "down")

    def working(symbol, quote, interval, start_ms, end_ms, max_candles, timeout):
        calls.append("okx")
        return [candle(start_ms // 1000, "1")]

    service = CandleService(FakePrices(["okx", "bybit"]), {"bybit": failing, "okx": working}, now=lambda: 10 * H)
    series = service.get_candles("BTC", "1h", H + 5, 3 * H)
    assert series.source == "okx" and calls == ["bybit", "okx"]   # Bybit preferred, falls back to OKX
    assert series.candles[0].time == H                              # start floored to the candle boundary
    service.get_candles("BTC", "1h", H + 5, 3 * H)
    assert calls == ["bybit", "okx"]                                # historical range served from cache

    with pytest.raises(AppError) as exc:
        CandleService(FakePrices([]), {}, now=lambda: 0).get_candles("NOPE", "1h", 0, H)
    assert exc.value.code == "candles.symbol_not_found"
    with pytest.raises(AppError) as exc:
        service.get_candles("BTC", "2x", 0, H)
    assert exc.value.code == "candles.invalid_interval"
