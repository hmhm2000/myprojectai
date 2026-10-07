"""OKX: GET /api/v5/market/tickers?instType=SPOT (publiczny, bez klucza API).

Jedno zapytanie zwraca wszystkie pary spot. Format pary: "BTC-USDT".
"""
from services.providers.base import ProviderError, Ticker, change_pct, get_json, to_decimal

TICKERS_URL = "https://www.okx.com/api/v5/market/tickers"


class OkxProvider:
    name = "okx"

    def fetch_tickers(self, quote: str, timeout: float) -> dict[str, Ticker]:
        payload = get_json(TICKERS_URL, {"instType": "SPOT"}, timeout, "OKX")
        if str(payload.get("code")) != "0":
            raise ProviderError(f"OKX: błąd API {payload.get('code')}: {payload.get('msg')}")
        return parse_tickers(payload.get("data") or [], quote)


def parse_tickers(items: list[dict], quote: str) -> dict[str, Ticker]:
    suffix = f"-{quote}"
    result: dict[str, Ticker] = {}
    for item in items:
        inst_id = item.get("instId")
        if not isinstance(inst_id, str) or not inst_id.endswith(suffix):
            continue
        symbol = inst_id[: -len(suffix)].upper()
        price = to_decimal(item.get("last"))
        if not symbol or price is None or price <= 0:
            continue
        result[symbol] = Ticker(symbol, price, change_pct(price, to_decimal(item.get("open24h"))))
    return result
