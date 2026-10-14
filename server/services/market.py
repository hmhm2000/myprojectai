"""Global market data: dominance of BTC / ETH / USDT and the total market cap.

Source: CoinGecko GET /api/v3/global (public, no API key) - current values only (the free API has no
history of dominance). Cached for 5 minutes; when CoinGecko fails, the last values are returned
marked as stale.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from core.errors import AppError
from services.providers.base import ProviderError, get_json

GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
TTL_SECONDS = 300
RETRY_SECONDS = 60


def parse_global(payload: dict) -> dict:
    data = payload.get("data") or {}
    share = data.get("market_cap_percentage") or {}
    pct = lambda key: float(share[key]) if key in share else None
    return {
        "btc_dominance": pct("btc"),
        "eth_dominance": pct("eth"),
        "usdt_dominance": pct("usdt"),
        "usdc_dominance": pct("usdc"),
        "total_market_cap_usd": (data.get("total_market_cap") or {}).get("usd"),
        "market_cap_change_24h_pct": data.get("market_cap_change_percentage_24h_usd"),
        "updated_at": data.get("updated_at"),
    }


class MarketService:
    def __init__(self, fetch: Callable[[], dict] = None, timeout: float = 10, now: Callable[[], float] = time.time):
        self._fetch = fetch or (lambda: get_json(GLOBAL_URL, {}, timeout, "CoinGecko"))
        self._now = now
        self._lock = threading.Lock()
        self._value: Optional[dict] = None
        self._fetched = 0.0
        self._failed = 0.0

    def get(self) -> dict:
        with self._lock:
            now = self._now()
            fresh = self._value is not None and now - self._fetched < TTL_SECONDS
            if not fresh and now - self._failed >= RETRY_SECONDS:
                try:
                    self._value = parse_global(self._fetch())
                    self._fetched = now
                except (ProviderError, ValueError, KeyError, TypeError):
                    self._failed = now
            if self._value is None:
                raise AppError(502, "market.unavailable", "Market data unavailable")
            return {**self._value, "source": "CoinGecko", "fetched_at": self._fetched,
                    "stale": now - self._fetched >= TTL_SECONDS}


market_service = MarketService()
