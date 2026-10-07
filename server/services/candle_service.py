"""Candles (OHLCV) from public exchange endpoints - shared by the chart, indicators, alerts and position timing.

- Source: Bybit when the pair is listed there (1000 candles per request), otherwise OKX
  (100 per request). If the first source fails, the next one is tried.
- Range cache: for every (source, symbol, native interval) one contiguous range of candles is kept
  in memory. A request inside that range is served without calling the exchange; otherwise only
  the missing part is fetched (older history, or the newest candles once LIVE_TTL_SECONDS passed).
  So the chart, each indicator and alerts share the same data, and switching intervals back and
  forth does not download the history again.
- Custom intervals (3d, 2w, 2h, 3M ...) are aggregated from their native base interval
  (see services/intervals.py) - the base candles come from the same cache.
"""
from __future__ import annotations

import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from functools import partial
from typing import Callable

from config import settings
from core.errors import AppError, NotFound
from services.intervals import Interval, aggregate, parse
from services.price_service import PriceService, price_service
from services.providers import bybit, okx
from services.providers.base import Candle, ProviderError

FETCHERS = {"bybit": bybit.fetch_candles, "okx": okx.fetch_candles,
            "bybit_perp": partial(bybit.fetch_candles, market="perp"),
            "okx_perp": partial(okx.fetch_candles, market="perp")}
SOURCE_PREFERENCE = ["bybit", "okx"]
PERP_SOURCES = ["bybit_perp", "okx_perp"]   # USDT perpetuals (e.g. PVSRA volume); not every coin has one
MISSING_SYMBOL_SECONDS = 600                # a source that does not list a symbol is skipped for it a while
LIVE_TTL_SECONDS = 30
SOURCE_BACKOFF_SECONDS = 30   # a source that just failed is skipped for a while (if another one exists)
MAX_STORES = 200            # (source, symbol, interval) ranges kept in memory
MAX_STORE_CANDLES = 100_000
MAX_CANDLES = 20_000        # per request (custom intervals need several base candles each)


@dataclass(frozen=True)
class CandleSeries:
    symbol: str
    interval: str
    source: str
    candles: list[Candle]

    def is_closed(self, candle: Candle, now: float) -> bool:
        """A candle is confirmed (closed) once its interval has fully passed."""
        return parse(self.interval).is_closed(candle.time, now)


@dataclass
class _Store:
    start: int                       # covered range [start, end] (unix s)
    end: int
    refreshed: float                 # last fetch that reached "now" (live data), 0 = never
    candles: dict[int, Candle] = field(default_factory=dict)


class CandleService:
    def __init__(self, prices: PriceService, fetchers: dict[str, Callable] = FETCHERS,
                 timeout: float = 10, now: Callable[[], float] = time.time):
        self._prices = prices
        self._fetchers = fetchers
        self._timeout = timeout
        self._now = now
        self._stores: OrderedDict[tuple, _Store] = OrderedDict()
        self._lock = threading.Lock()
        self._key_locks: dict[tuple, threading.Lock] = {}
        self._failed_until: dict[str, float] = {}
        self._missing_until: dict[tuple[str, str], float] = {}

    # ------------------------------------------------------------------ public

    def get_candles(self, symbol: str, interval: str, start: int, end: int,
                    max_candles: int = MAX_CANDLES, market: str = "spot") -> CandleSeries:
        """Candles overlapping [start, end] (unix s), oldest first (at most `max_candles`, the newest).
        market "perp": the coin's USDT perpetual (Bybit linear / OKX swap) instead of spot."""
        spec = parse(interval)
        base = spec.base
        now = self._now()
        start = spec.bucket_start(max(start, 0))      # include the candle that contains `start`
        end = min(end, int(now))
        base_count = min(MAX_CANDLES, math.ceil((end - start) / base.seconds) + 2)

        if market == "perp":
            sources = [s for s in PERP_SOURCES if s in self._fetchers
                       and self._missing_until.get((s, symbol), 0) <= now]
        else:
            sources = [s for s in SOURCE_PREFERENCE if s in self._prices.sources_for(symbol) and s in self._fetchers]
        if not sources:
            raise NotFound("candles.symbol_not_found", f"No exchange lists {symbol}", symbol=symbol)
        healthy = [s for s in sources if self._failed_until.get(s, 0) <= now]
        sources = healthy or sources

        last_error: ProviderError | None = None
        for source in sources:
            try:
                candles = self._native(source, symbol, base, start, end, base_count, now)
            except ProviderError as exc:
                last_error = exc
                if exc.code == "api_error":       # e.g. the symbol is not listed there - only this symbol
                    self._missing_until[(source, symbol)] = now + MISSING_SYMBOL_SECONDS
                else:
                    self._failed_until[source] = now + SOURCE_BACKOFF_SECONDS
                continue
            if not spec.native:
                candles = aggregate(candles, spec)
            return CandleSeries(symbol, spec.name, source, candles[-max_candles:])
        raise AppError(502, "candles.unavailable", f"Candles unavailable: {last_error}",
                       source_error=last_error.code if last_error else None)

    # ----------------------------------------------------------------- private

    def _fetch(self, source: str, symbol: str, spec: Interval, start: int, end: int) -> list[Candle]:
        count = min(MAX_CANDLES, math.ceil((end - start) / spec.seconds) + 2)
        return self._fetchers[source](symbol, self._prices.quote_currency, spec.name,
                                      start * 1000, end * 1000, count, self._timeout)

    def _native(self, source: str, symbol: str, spec: Interval, start: int, end: int,
                max_candles: int, now: float) -> list[Candle]:
        key = (source, symbol, spec.name)
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:                                  # one fetch per range at a time
            with self._lock:
                store = self._stores.get(key)
            live = end >= now - spec.seconds

            if store is None:
                # `refreshed` = time of the last fetch that reached "now" (0 = newest candles never fetched)
                store = _Store(start, end, now if live else 0.0)
                store.candles.update({c.time: c for c in self._fetch(source, symbol, spec, start, end)})
            else:
                if start < store.start:                  # older history -> fetch only that part
                    older = self._fetch(source, symbol, spec, start, store.start - 1)
                    store.candles.update({c.time: c for c in older})
                    store.start = start
                stale_tail = now - store.refreshed >= LIVE_TTL_SECONDS
                if (live and stale_tail) or (not live and end > store.end):
                    # newest candles: from the last stored one (it may have been still forming)
                    stored = [t for t in store.candles if t <= store.end]
                    tail_from = max(stored) if stored else store.start
                    newer = self._fetch(source, symbol, spec, tail_from, end)
                    store.candles.update({c.time: c for c in newer})
                    store.end = max(store.end, end)
                    if live:
                        store.refreshed = now

            with self._lock:
                if len(store.candles) <= MAX_STORE_CANDLES:
                    self._stores[key] = store
                    self._stores.move_to_end(key)
                    while len(self._stores) > MAX_STORES:
                        self._stores.popitem(last=False)
                else:
                    self._stores.pop(key, None)

            selected = sorted((c for t, c in store.candles.items() if start <= t <= end), key=lambda c: c.time)
            return selected[-max_candles:]


candle_service = CandleService(price_service, timeout=settings.price_http_timeout_seconds)
