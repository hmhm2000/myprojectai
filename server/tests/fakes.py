from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.price_service import PriceService
from services.providers.base import ProviderError, Ticker


class FakeClock:
    def __init__(self):
        self.mono = 1000.0
        self.start = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.mono

    def now(self) -> datetime:
        return self.start + timedelta(seconds=self.mono - 1000.0)

    def advance(self, seconds: float) -> None:
        self.mono += seconds


class FakeProvider:
    def __init__(self, name: str, prices: dict[str, str]):
        self.name = name
        self.prices = prices
        self.calls = 0
        self.error: ProviderError | None = None

    def fetch_tickers(self, quote: str, timeout: float) -> dict[str, Ticker]:
        self.calls += 1
        if self.error:
            raise self.error
        return {s: Ticker(s, Decimal(p), Decimal("1.5")) for s, p in self.prices.items()}


def make_service(clock: FakeClock, *providers: FakeProvider, ttl=180, force_interval=10, backoff=30) -> PriceService:
    return PriceService(
        providers=list(providers),
        quote_currency="USDT",
        ttl_seconds=ttl,
        force_min_interval_seconds=force_interval,
        error_backoff_seconds=backoff,
        http_timeout_seconds=1,
        monotonic=clock.monotonic,
        now=clock.now,
    )
