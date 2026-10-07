from decimal import Decimal

import pytest

from services.price_service import RefreshTooSoon
from services.providers import bybit, okx
from services.providers.base import ProviderError
from tests.fakes import FakeClock, FakeProvider, make_service


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def okx_fake():
    return FakeProvider("okx", {"BTC": "60000", "ETH": "2500"})


@pytest.fixture
def bybit_fake():
    return FakeProvider("bybit", {"BTC": "60010", "SPX": "0.42"})


def test_cache_is_used_until_ttl_expires(clock, okx_fake, bybit_fake):
    service = make_service(clock, okx_fake, bybit_fake)

    service.get_snapshot()
    service.get_snapshot()
    clock.advance(179)
    service.get_snapshot()
    assert (okx_fake.calls, bybit_fake.calls) == (1, 1)

    clock.advance(2)  # 181 s > TTL
    snapshot = service.get_snapshot()
    assert (okx_fake.calls, bybit_fake.calls) == (2, 2)
    assert snapshot.stale is False


def test_okx_has_priority_and_bybit_fills_missing_coins(clock, okx_fake, bybit_fake):
    quotes = make_service(clock, okx_fake, bybit_fake).get_snapshot().quotes
    assert quotes["BTC"].price == Decimal("60000")
    assert quotes["BTC"].source == "okx"
    assert quotes["SPX"].price == Decimal("0.42")
    assert quotes["SPX"].source == "bybit"
    assert set(quotes) == {"BTC", "ETH", "SPX"}


def test_failure_keeps_last_prices_marked_stale_and_backs_off(clock, okx_fake, bybit_fake):
    service = make_service(clock, okx_fake, bybit_fake, backoff=30)
    first = service.get_snapshot()

    clock.advance(200)
    okx_fake.error = ProviderError("connection_error", "OKX: connection failed")
    snapshot = service.get_snapshot()

    assert snapshot.stale is True
    assert snapshot.quotes["ETH"].price == Decimal("2500")      # last known price
    assert snapshot.quotes["ETH"].stale is True
    assert snapshot.quotes["SPX"].stale is False                 # Bybit still works
    okx_status = next(s for s in snapshot.sources if s.name == "okx")
    assert okx_status.error == "OKX: connection failed"
    assert okx_status.error_code == "connection_error"
    assert okx_status.fetched_at == first.sources[0].fetched_at  # "stale since..."
    assert snapshot.fetched_at == first.fetched_at

    # During backoff the exchange is not queried again.
    calls = okx_fake.calls
    clock.advance(10)
    service.get_snapshot()
    assert okx_fake.calls == calls

    # After backoff: another attempt; the exchange is back.
    okx_fake.error = None
    clock.advance(21)
    snapshot = service.get_snapshot()
    assert okx_fake.calls == calls + 1
    assert snapshot.stale is False


def test_rate_limit_retry_after_extends_backoff(clock, okx_fake):
    service = make_service(clock, okx_fake, backoff=30)
    okx_fake.error = ProviderError("rate_limited", "OKX: HTTP 429", retry_after=120)
    service.get_snapshot()
    clock.advance(100)
    service.get_snapshot()
    assert okx_fake.calls == 1
    clock.advance(21)
    service.get_snapshot()
    assert okx_fake.calls == 2


def test_force_refresh_has_minimum_interval(clock, okx_fake):
    service = make_service(clock, okx_fake, force_interval=10)
    service.get_snapshot()
    assert okx_fake.calls == 1

    service.force_refresh()  # cache is fresh, but we force it
    assert okx_fake.calls == 2

    clock.advance(3)
    with pytest.raises(RefreshTooSoon) as exc:
        service.force_refresh()
    assert exc.value.retry_after == 7
    assert okx_fake.calls == 2
    assert service.get_snapshot().force_available_in == 7

    clock.advance(7)
    service.force_refresh()
    assert okx_fake.calls == 3


def test_okx_parser():
    items = [
        {"instId": "BTC-USDT", "last": "60000.1", "open24h": "50000"},
        {"instId": "BTC-USDC", "last": "60001"},
        {"instId": "BAD-USDT", "last": ""},
        {"instId": "ZERO-USDT", "last": "0"},
    ]
    result = okx.parse_tickers(items, "USDT")
    assert list(result) == ["BTC"]
    assert result["BTC"].price == Decimal("60000.1")
    assert result["BTC"].change_24h_pct == Decimal("20.00")


def test_bybit_parser():
    items = [
        {"symbol": "SPXUSDT", "lastPrice": "0.4222", "prevPrice24h": "0.5"},
        {"symbol": "SPXUSDC", "lastPrice": "0.4195"},
        {"symbol": "ETHBTC", "lastPrice": "0.04"},
    ]
    result = bybit.parse_tickers(items, "USDT")
    assert list(result) == ["SPX"]
    assert result["SPX"].change_24h_pct == Decimal("-15.56")
