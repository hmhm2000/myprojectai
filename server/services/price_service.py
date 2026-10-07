"""Cache cen z giełd.

- Jedno zbiorcze zapytanie na giełdę (OKX + Bybit, równolegle), bez kluczy API.
- Pobranie przy starcie, potem odświeżanie "leniwe": dopiero gdy ktoś poprosi
  o ceny, a dane są starsze niż TTL. Gdy nikt nie korzysta z aplikacji, nic nie jest pobierane.
- Wymuszone odświeżenie (przycisk "Odśwież ceny") ma minimalny odstęp.
- Przy błędzie giełdy zostają ostatnie znane ceny, oznaczone jako nieaktualne,
  a kolejna próba następuje dopiero po czasie backoff (lub Retry-After).
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
        super().__init__(f"Odczekaj {retry_after} s przed kolejnym odświeżeniem")
        self.retry_after = retry_after


@dataclass
class _SourceState:
    tickers: dict[str, Ticker] = field(default_factory=dict)
    fetched_at: Optional[datetime] = None        # ostatnie udane pobranie (do wyświetlenia)
    fetched_mono: Optional[float] = None         # to samo, zegar monotoniczny (do liczenia wieku)
    error: Optional[str] = None                  # błąd ostatniej próby (None = OK)
    retry_not_before_mono: float = 0.0           # backoff po błędzie


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
    count: int


@dataclass(frozen=True)
class Snapshot:
    quote_currency: str
    quotes: dict[str, Quote]
    sources: list[SourceStatus]
    fetched_at: Optional[datetime]      # najstarsze z udanych pobrań (od kiedy dane mogą być nieaktualne)
    stale: bool
    ttl_seconds: int
    force_available_in: int             # za ile sekund można wymusić odświeżenie


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
        self._providers = providers                  # kolejność = priorytet źródła ceny
        self._quote = quote_currency
        self._ttl = ttl_seconds
        self._force_interval = force_min_interval_seconds
        self._backoff = error_backoff_seconds
        self._timeout = http_timeout_seconds
        self._monotonic = monotonic
        self._now = now

        self._state = {p.name: _SourceState() for p in providers}
        self._state_lock = threading.Lock()
        self._refresh_lock = threading.Lock()        # tylko jedno pobieranie naraz
        self._last_force_mono: Optional[float] = None

    # ------------------------------------------------------------------ public

    def get_snapshot(self) -> Snapshot:
        """Ceny z cache; giełdy są odpytywane tylko, gdy cache jest nieświeży."""
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

    def warm_up_in_background(self) -> None:
        """Pierwsze pobranie przy starcie serwera, bez blokowania startu."""
        threading.Thread(target=self._safe_initial_refresh, name="price-warmup", daemon=True).start()

    # ----------------------------------------------------------------- private

    def _safe_initial_refresh(self) -> None:
        try:
            self._refresh(force=True)
        except Exception:  # pragma: no cover - zabezpieczenie wątku
            logger.exception("Błąd pierwszego pobrania cen")

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
            # Sprawdzamy ponownie: inny wątek mógł właśnie skończyć pobieranie.
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
                    except Exception as exc:  # nieprzewidziany błąd parsera itp.
                        logger.exception("Nieoczekiwany błąd pobierania cen z %s", name)
                        results[name] = ProviderError(f"{name}: nieoczekiwany błąd ({exc.__class__.__name__})")

            with self._state_lock:
                for name, result in results.items():
                    state = self._state[name]
                    if isinstance(result, ProviderError):
                        state.error = str(result)
                        backoff = max(self._backoff, result.retry_after or 0)
                        state.retry_not_before_mono = self._monotonic() + backoff
                        logger.warning("Ceny z %s niedostępne: %s (ponowna próba za %s s)", name, result, backoff)
                    else:
                        state.tickers = result
                        state.fetched_at = self._now()
                        state.fetched_mono = self._monotonic()
                        state.error = None
                        state.retry_not_before_mono = 0.0
                        logger.info("Pobrano %d cen z %s", len(result), name)

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
                    count=len(state.tickers),
                ))
                for symbol, ticker in state.tickers.items():
                    if symbol not in quotes:  # pierwszeństwo ma wcześniejszy provider (OKX)
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
