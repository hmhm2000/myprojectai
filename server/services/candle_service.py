"""Candles (OHLCV) from public exchange endpoints - shared by position timing, the chart and (later) alerts.

- Source: Bybit when the pair is listed there (1000 candles per request), otherwise OKX
  (100 per request). If the first source fails, the next one is tried.
- Cache: ranges reaching "now" are cached for LIVE_TTL_SECONDS; historical ranges never change,
  so they are kept until evicted (LRU, MAX_ENTRIES).
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable

from config import settings
from core.errors import AppError, BadRequest, NotFound
from services.price_service import PriceService, price_service
from services.providers import bybit, okx
from services.providers.base import INTERVAL_SECONDS, Candle, ProviderError

FETCHERS = {"bybit": bybit.fetch_candles, "okx": okx.fetch_candles}
SOURCE_PREFERENCE = ["bybit", "okx"]
LIVE_TTL_SECONDS = 30
MAX_ENTRIES = 300
MAX_CANDLES = 5000


@dataclass(frozen=True)
class CandleSeries:
    symbol: str
    interval: str
    source: str
    candles: list[Candle]

    def is_closed(self, candle: Candle, now: float) -> bool:
        """A candle is confirmed (closed) once its interval has fully passed."""
        return candle.time + INTERVAL_SECONDS[self.interval] <= now


class CandleService:
    def __init__(self, prices: PriceService, fetchers: dict[str, Callable] = FETCHERS,
                 timeout: float = 10, now: Callable[[], float] = time.time):
        self._prices = prices
        self._fetchers = fetchers
        self._timeout = timeout
        self._now = now
        self._cache: OrderedDict[tuple, tuple[float | None, CandleSeries]] = OrderedDict()
        self._lock = threading.Lock()

    def get_candles(self, symbol: str, interval: str, start: int, end: int,
                    max_candles: int = MAX_CANDLES) -> CandleSeries:
        """Candles overlapping [start, end] (unix seconds), oldest first."""
        if interval not in INTERVAL_SECONDS:
            raise BadRequest("candles.invalid_interval", f"Unsupported interval: {interval}", interval=interval)
        step = INTERVAL_SECONDS[interval]
        now = self._now()
        start = start // step * step                  # include the candle that contains `start`
        end = min(end, int(now))
        live = end >= now - step
        cache_end = end // step * step if live else end

        sources = [s for s in SOURCE_PREFERENCE if s in self._prices.sources_for(symbol) and s in self._fetchers]
        if not sources:
            raise NotFound("candles.symbol_not_found", f"No exchange lists {symbol}", symbol=symbol)

        key = (symbol, interval, start, cache_end, max_candles)
        with self._lock:
            cached = self._cache.get(key)
            if cached and (cached[0] is None or cached[0] > now):
                self._cache.move_to_end(key)
                return cached[1]

        last_error: ProviderError | None = None
        for source in sources:
            try:
                candles = self._fetchers[source](symbol, self._prices.quote_currency, interval,
                                                 start * 1000, end * 1000, max_candles, self._timeout)
            except ProviderError as exc:
                last_error = exc
                continue
            series = CandleSeries(symbol, interval, source, candles)
            with self._lock:
                self._cache[key] = (now + LIVE_TTL_SECONDS if live else None, series)
                self._cache.move_to_end(key)
                while len(self._cache) > MAX_ENTRIES:
                    self._cache.popitem(last=False)
            return series
        raise AppError(502, "candles.unavailable", f"Candles unavailable: {last_error}",
                       source_error=last_error.code if last_error else None)


candle_service = CandleService(price_service, timeout=settings.price_http_timeout_seconds)
