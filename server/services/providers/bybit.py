"""Bybit: GET /v5/market/tickers?category=spot (publiczny, bez klucza API).

Jedno zapytanie zwraca wszystkie pary spot. Format pary: "SPXUSDT" (bez separatora).
"""
from services.providers.base import ProviderError, Ticker, change_pct, get_json, to_decimal

TICKERS_URL = "https://api.bybit.com/v5/market/tickers"


class BybitProvider:
    name = "bybit"

    def fetch_tickers(self, quote: str, timeout: float) -> dict[str, Ticker]:
        payload = get_json(TICKERS_URL, {"category": "spot"}, timeout, "Bybit")
        if payload.get("retCode") != 0:
            raise ProviderError(f"Bybit: błąd API {payload.get('retCode')}: {payload.get('retMsg')}")
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
