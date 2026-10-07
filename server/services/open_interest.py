"""Open interest of USDT perpetuals from public exchange endpoints (no API key).

- Bybit: GET /v5/market/open-interest (category=linear, 200 points per page, cursor paging),
- OKX:   GET /api/v5/rubik/stat/contracts/open-interest-history (instId <COIN>-USDT-SWAP, 100 per page).
A point (t, oi) is the open interest AT time t. The OI "close" of a candle is the point at the candle's
end - see indicators/context.py. Periods: 5m 15m 30m 1h 4h 1d (other intervals use the largest one
that divides them; 1m uses 5m). Results are cached per (symbol, period) and refreshed after a minute.
"""
from __future__ import annotations

import threading
import time
from typing import Callable

from config import settings
from core.errors import AppError, NotFound
from services.intervals import parse
from services.providers.base import ProviderError, get_json, to_decimal

PERIODS = ["5m", "15m", "30m", "1h", "4h", "1d"]                 # supported by both exchanges
BYBIT_URL = "https://api.bybit.com/v5/market/open-interest"
BYBIT_PERIODS = {"5m": "5min", "15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "1d"}
OKX_URL = "https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-history"
OKX_PERIODS = {"5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D"}
REFRESH_SECONDS = 60
MAX_PAGES = 40
MAX_CACHE = 100


def period_for(interval: str) -> str:
    """OI period used for a chart interval: the largest supported one that divides it."""
    spec = parse(interval)
    if spec.unit in ("d", "w", "M"):
        return "1d"
    seconds = spec.seconds
    fitting = [p for p in PERIODS if parse(p).seconds <= seconds and seconds % parse(p).seconds == 0]
    return fitting[-1] if fitting else PERIODS[0]


def fetch_bybit(symbol: str, quote: str, period: str, start: int, end: int, timeout: float) -> list[tuple[int, float]]:
    points: dict[int, float] = {}
    cursor = None
    for _ in range(MAX_PAGES):
        params = {"category": "linear", "symbol": f"{symbol}{quote}", "intervalTime": BYBIT_PERIODS[period],
                  "startTime": str(start * 1000), "endTime": str(end * 1000), "limit": "200"}
        if cursor:
            params["cursor"] = cursor
        payload = get_json(BYBIT_URL, params, timeout, "Bybit")
        if payload.get("retCode") != 0:
            raise ProviderError("api_error", f"Bybit: API error {payload.get('retCode')}: {payload.get('retMsg')}")
        result = payload.get("result") or {}
        for row in result.get("list") or []:
            value = to_decimal(row.get("openInterest"))
            if value is not None and row.get("timestamp"):
                points[int(row["timestamp"]) // 1000] = float(value)
        cursor = result.get("nextPageCursor")
        if not cursor or not result.get("list"):
            break
    return sorted(points.items())


def fetch_okx(symbol: str, quote: str, period: str, start: int, end: int, timeout: float) -> list[tuple[int, float]]:
    points: dict[int, float] = {}
    cursor = end * 1000
    for _ in range(MAX_PAGES):
        payload = get_json(OKX_URL, {"instId": f"{symbol}-{quote}-SWAP", "period": OKX_PERIODS[period],
                                     "begin": str(start * 1000), "end": str(cursor), "limit": "100"}, timeout, "OKX")
        if str(payload.get("code")) != "0":
            raise ProviderError("api_error", f"OKX: API error {payload.get('code')}: {payload.get('msg')}")
        rows = payload.get("data") or []
        for row in rows:
            value = to_decimal(row[2]) if len(row) > 2 else None      # oiCcy = open interest in coins (like Bybit)
            if value is not None:
                points[int(row[0]) // 1000] = float(value)
        if len(rows) < 100:
            break
        cursor = min(int(r[0]) for r in rows) - 1
        if cursor <= start * 1000:
            break
    return sorted(points.items())


FETCHERS: dict[str, Callable] = {"bybit": fetch_bybit, "okx": fetch_okx}


class OpenInterestService:
    def __init__(self, quote: str = "USDT", fetchers: dict[str, Callable] = FETCHERS, timeout: float = 10,
                 now: Callable[[], float] = time.time):
        self._quote = quote
        self._fetchers = fetchers
        self._timeout = timeout
        self._now = now
        self._cache: dict[tuple[str, str], tuple[int, float, list[tuple[int, float]]]] = {}
        self._lock = threading.Lock()

    def get(self, symbol: str, period: str, start: int, end: int) -> list[tuple[int, float]]:
        """(time, open interest) points in [start, end], oldest first."""
        now = self._now()
        key = (symbol, period)
        with self._lock:
            cached = self._cache.get(key)
        if cached and cached[0] <= start and now - cached[1] < REFRESH_SECONDS:
            return [p for p in cached[2] if start <= p[0] <= end]
        last_error = None
        for name, fetch in self._fetchers.items():
            try:
                points = fetch(symbol, self._quote, period, start, int(now), self._timeout)
            except ProviderError as exc:
                last_error = exc
                continue
            if not points:
                continue
            with self._lock:
                self._cache[key] = (start, now, points)
                while len(self._cache) > MAX_CACHE:
                    self._cache.pop(next(iter(self._cache)))
            return [p for p in points if start <= p[0] <= end]
        if last_error and last_error.code != "api_error":
            raise AppError(502, "candles.unavailable", f"Open interest unavailable: {last_error}")
        raise NotFound("candles.symbol_not_found", f"No open interest for {symbol}", symbol=symbol)


open_interest_service = OpenInterestService(settings.quote_currency, timeout=settings.price_http_timeout_seconds)
