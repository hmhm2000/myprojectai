import pytest

from core.errors import AppError
from services.market import MarketService

PAYLOAD = {"data": {"market_cap_percentage": {"btc": 59.3, "eth": 10.7, "usdt": 6.6, "usdc": 2.6},
                    "total_market_cap": {"usd": 2.77e12}, "market_cap_change_percentage_24h_usd": -4.25,
                    "updated_at": 1791988027}}


def test_market_values_cache_and_stale_fallback():
    clock = {"now": 1000.0}
    calls = []

    def fetch():
        calls.append(clock["now"])
        if len(calls) > 1:
            from services.providers.base import ProviderError
            raise ProviderError("connection_error", "down")
        return PAYLOAD

    service = MarketService(fetch, now=lambda: clock["now"])
    first = service.get()
    assert (first["btc_dominance"], first["usdt_dominance"], first["total_market_cap_usd"]) == (59.3, 6.6, 2.77e12)
    assert first["stale"] is False and first["source"] == "CoinGecko"
    clock["now"] += 100
    service.get()
    assert len(calls) == 1                                               # cached for 5 minutes
    clock["now"] += 300
    stale = service.get()                                                # CoinGecko down: last values, stale
    assert len(calls) == 2 and stale["stale"] is True and stale["btc_dominance"] == 59.3
    clock["now"] += 10
    service.get()
    assert len(calls) == 2                                               # no retry for a minute


def test_market_unavailable_without_any_data():
    from services.providers.base import ProviderError

    def fetch():
        raise ProviderError("connection_error", "down")

    with pytest.raises(AppError):
        MarketService(fetch).get()
