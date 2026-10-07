"""Bybit: GET /v5/market/tickers?category=spot (public, no API key).

One request returns all spot pairs. Pair format: "SPXUSDT" (no separator).
"""
from services.providers.base import Candle, ProviderError, Ticker, change_pct, get_json, parse_candle_row, to_decimal

TICKERS_URL = "https://api.bybit.com/v5/market/tickers"


class BybitProvider:
    name = "bybit"

    def fetch_tickers(self, quote: str, timeout: float) -> dict[str, Ticker]:
        payload = get_json(TICKERS_URL, {"category": "spot"}, timeout, "Bybit")
        if payload.get("retCode") != 0:
            raise ProviderError("api_error", f"Bybit: API error {payload.get('retCode')}: {payload.get('retMsg')}")
        return parse_tickers((payload.get("result") or {}).get("list") or [], quote)


def parse_tickers(items: list[dict], quote: str) -> dict[str, Ticker]:
    result: dict[str, Ticker] = {}
    for item in items:
        pair = item.get("symbol")
        if not isinstance(pair, str) or not pair.endswith(quote):
            continue
        symbol = pair[: -len(quote)].upper()
        price = to_decimal(item.get("lastPrice"))
        if not symbol or price is None or price <= 0:
            continue
        result[symbol] = Ticker(symbol, price, change_pct(price, to_decimal(item.get("prevPrice24h"))))
    return result


CANDLES_URL = "https://api.bybit.com/v5/market/kline"
BYBIT_INTERVALS = {"1m": "1", "5m": "5", "15m": "15", "30m": "30", "1h": "60", "4h": "240", "1d": "D"}
BYBIT_PAGE = 1000  # kline returns at most 1000 rows per request


def fetch_candles(symbol: str, quote: str, interval: str, start_ms: int, end_ms: int,
                  max_candles: int, timeout: float) -> list[Candle]:
    """Candles in [start_ms, end_ms], oldest first. Pages backwards from end_ms."""
    candles: dict[int, Candle] = {}
    cursor = end_ms
    while len(candles) < max_candles:
        payload = get_json(CANDLES_URL, {"category": "spot", "symbol": f"{symbol}{quote}",
                                         "interval": BYBIT_INTERVALS[interval], "start": str(start_ms),
                                         "end": str(cursor), "limit": str(BYBIT_PAGE)}, timeout, "Bybit")
        if payload.get("retCode") != 0:
            raise ProviderError("api_error", f"Bybit: API error {payload.get('retCode')}: {payload.get('retMsg')}")
        rows = (payload.get("result") or {}).get("list") or []
        page = [c for c in (parse_candle_row(r) for r in rows) if c]
        for candle in page:
            candles[candle.time] = candle
        if len(rows) < BYBIT_PAGE or not page:
            break
        cursor = min(c.time for c in page) * 1000 - 1
    return sorted(candles.values(), key=lambda c: c.time)[-max_candles:]
