from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Protocol

import requests


@dataclass(frozen=True)
class Ticker:
    symbol: str                      # coin bazowy, np. "BTC"
    price: Decimal                   # ostatnia cena w walucie kwotowania
    change_24h_pct: Optional[Decimal]


class ProviderError(Exception):
    """Giełda nie zwróciła poprawnych danych."""

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class PriceProvider(Protocol):
    name: str

    def fetch_tickers(self, quote: str, timeout: float) -> dict[str, Ticker]:
        """Jedno zbiorcze zapytanie: wszystkie pary SPOT w danej walucie kwotowania."""
        ...


def to_decimal(value) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def change_pct(price: Decimal, open_24h: Optional[Decimal]) -> Optional[Decimal]:
    if open_24h is None or open_24h <= 0:
        return None
    return ((price - open_24h) / open_24h * 100).quantize(Decimal("0.01"))


def get_json(url: str, params: dict, timeout: float, exchange: str) -> dict:
    try:
        response = requests.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise ProviderError(f"{exchange}: brak połączenia ({exc.__class__.__name__})") from exc

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        raise ProviderError(
            f"{exchange}: przekroczony limit zapytań (HTTP 429)",
            retry_after=int(retry_after) if retry_after and retry_after.isdigit() else None,
        )
    if response.status_code != 200:
        raise ProviderError(f"{exchange}: HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(f"{exchange}: niepoprawna odpowiedź (nie JSON)") from exc
