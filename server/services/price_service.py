"""Exchange price cache.

- One bulk request per exchange (OKX + Bybit, in parallel), no API keys.
- Fetched on startup, then refreshed lazily: only when someone asks for prices
  and the data is older than the TTL. Nothing is fetched while nobody uses the app.
- A forced refresh ("Refresh prices" button) has a minimum interval.
- When an exchange fails, the last known prices are kept and marked as stale;
  the next attempt happens only after the backoff time (or the exchange's Retry-After).
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional

from config import settings
from services.providers.base import PriceProvider, ProviderError, Ticker
from services.providers.bybit import BybitProvider
from services.providers.okx import OkxProvider

logger = logging.getLogger(__name__)


class RefreshTooSoon(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"Wait {retry_after} s before the next forced refresh")
        self.retry_after = retry_after


@dataclass
class _SourceState:
    tickers: dict[str, Ticker] = field(default_factory=dict)
    fetched_at: Optional[datetime] = None        # last successful fetch (for display)
    fetched_mono: Optional[float] = None         # same, monotonic clock (for age calculation)
    error: Optional[str] = None                  # English description of the last failure (None = OK)
    error_code: Optional[str] = None             # stable code of the last failure, translated by the frontend
    retry_not_before_mono: float = 0.0           # backoff after an error


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    change_24h_pct: Optional[Decimal]
    source: str
    stale: bool


@dataclass(frozen=True)
class SourceStatus:
    name: str
    ok: bool
    fetched_at: Optional[datetime]
    stale: bool
    error: Optional[str]
    error_code: Optional[str]
    count: int


@dataclass(frozen=True)
class Snapshot:
    quote_currency: str
    quotes: dict[str, Quote]
    sources: list[SourceStatus]
    fetched_at: Optional[datetime]      # oldest successful fetch (since when data may be stale)
    stale: bool
    ttl_seconds: int
    force_available_in: int             # seconds until a forced refresh is allowed


class PriceService:
    def __init__(
        self,
        providers: list[PriceProvider],
        quote_currency: str,
        ttl_seconds: int,
        force_min_interval_seconds: int,
        error_backoff_seconds: int,
        http_timeout_seconds: float,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._providers = providers                  # order = price source priority
        self._quote = quote_currency
        self._ttl = ttl_seconds
        self._force_interval = force_min_interval_seconds
        self._backoff = error_backoff_seconds
        self._timeout = http_timeout_seconds
        self._monotonic = monotonic
        self._now = now

        self._state = {p.name: _SourceState() for p in providers}
        self._state_lock = threading.Lock()
        self._refresh_lock = threading.Lock()        # only one fetch at a time
        self._last_force_mono: Optional[float] = None

    # ------------------------------------------------------------------ public

    def get_snapshot(self) -> Snapshot:
        """Prices from the cache; exchanges are queried only when the cache is stale."""
        if self._sources_to_refresh(force=False):
            self._refresh(force=False)
        return self._build_snapshot()

    def force_refresh(self) -> Snapshot:
        with self._state_lock:
            wait = self._force_wait_seconds()
            if wait > 0:
                raise RefreshTooSoon(wait)
            self._last_force_mono = self._monotonic()
        self._refresh(force=True)
        return self._build_snapshot()

    def sources_for(self, symbol: str) -> list[str]:
        """Names of the providers that list the symbol (in priority order), based on the cached tickers."""
        if self._sources_to_refresh(force=False):
            self._refresh(force=False)
        with self._state_lock:
            return [p.name for p in self._providers if symbol in self._state[p.name].tickers]

    @property
    def quote_currency(self) -> str:
        return self._quote

    def warm_up_in_background(self) -> None:
        """First fetch on server start, without blocking the startup."""
        threading.Thread(target=self._safe_initial_refresh, name="price-warmup", daemon=True).start()

    # ----------------------------------------------------------------- private

    def _safe_initial_refresh(self) -> None:
        try:
            self._refresh(force=True)
        except Exception:  # pragma: no cover - thread safety net
            logger.exception("Initial price fetch failed")

    def _is_fresh(self, state: _SourceState) -> bool:
        return (
            state.error is None
            and state.fetched_mono is not None
            and self._monotonic() - state.fetched_mono < self._ttl
        )

    def _sources_to_refresh(self, force: bool) -> list[PriceProvider]:
        now = self._monotonic()
        with self._state_lock:
            result = []
            for provider in self._providers:
                state = self._state[provider.name]
                if force:
                    result.append(provider)
                elif not self._is_fresh(state) and now >= state.retry_not_before_mono:
                    result.append(provider)
            return result

    def _refresh(self, force: bool) -> None:
        with self._refresh_lock:
            # Check again: another thread may have just finished fetching.
            providers = self._sources_to_refresh(force)
            if not providers:
                return
            with ThreadPoolExecutor(max_workers=len(providers)) as pool:
                futures = {p.name: pool.submit(p.fetch_tickers, self._quote, self._timeout) for p in providers}
                results = {}
                for name, future in futures.items():
                    try:
                        results[name] = future.result()
                    except ProviderError as exc:
                        results[name] = exc
                    except Exception as exc:  # unexpected parser error etc.
                        logger.exception("Unexpected error while fetching prices from %s", name)
                        results[name] = ProviderError("unexpected_error", f"{name}: unexpected error ({exc.__class__.__name__})")

            with self._state_lock:
                for name, result in results.items():
                    state = self._state[name]
                    if isinstance(result, ProviderError):
                        state.error = str(result)
                        state.error_code = result.code
                        backoff = max(self._backoff, result.retry_after or 0)
                        state.retry_not_before_mono = self._monotonic() + backoff
                        logger.warning("Prices from %s unavailable: %s (retry in %s s)", name, result, backoff)
                    else:
                        state.tickers = result
                        state.fetched_at = self._now()
                        state.fetched_mono = self._monotonic()
                        state.error = None
                        state.error_code = None
                        state.retry_not_before_mono = 0.0
                        logger.info("Fetched %d prices from %s", len(result), name)

    def _force_wait_seconds(self) -> int:
        if self._last_force_mono is None:
            return 0
        remaining = self._force_interval - (self._monotonic() - self._last_force_mono)
        return max(0, int(remaining + 0.999))

    def _build_snapshot(self) -> Snapshot:
        with self._state_lock:
            quotes: dict[str, Quote] = {}
            sources: list[SourceStatus] = []
            for provider in self._providers:
                state = self._state[provider.name]
                stale = not self._is_fresh(state)
                sources.append(SourceStatus(
                    name=provider.name,
                    ok=state.error is None and state.fetched_at is not None,
                    fetched_at=state.fetched_at,
                    stale=stale,
                    error=state.error,
                    error_code=state.error_code,
                    count=len(state.tickers),
                ))
                for symbol, ticker in state.tickers.items():
                    if symbol not in quotes:  # earlier provider (OKX) wins
                        quotes[symbol] = Quote(symbol, ticker.price, ticker.change_24h_pct, provider.name, stale)

            fetched = [s.fetched_at for s in sources if s.fetched_at is not None]
            return Snapshot(
                quote_currency=self._quote,
                quotes=quotes,
                sources=sources,
                fetched_at=min(fetched) if fetched else None,
                stale=any(s.stale for s in sources),
                ttl_seconds=self._ttl,
                force_available_in=self._force_wait_seconds(),
            )


price_service = PriceService(
    providers=[OkxProvider(), BybitProvider()],
    quote_currency=settings.quote_currency,
    ttl_seconds=settings.price_ttl_seconds,
    force_min_interval_seconds=settings.price_force_min_interval_seconds,
    error_backoff_seconds=settings.price_error_backoff_seconds,
    http_timeout_seconds=settings.price_http_timeout_seconds,
)
