"""OKX: GET /api/v5/market/tickers?instType=SPOT (public, no API key).

One request returns all spot pairs. Pair format: "BTC-USDT".
"""
from services.providers.base import Candle, ProviderError, Ticker, change_pct, get_json, parse_candle_row, to_decimal

TICKERS_URL = "https://www.okx.com/api/v5/market/tickers"


class OkxProvider:
    name = "okx"

    def fetch_tickers(self, quote: str, timeout: float) -> dict[str, Ticker]:
        payload = get_json(TICKERS_URL, {"instType": "SPOT"}, timeout, "OKX")
        if str(payload.get("code")) != "0":
            raise ProviderError("api_error", f"OKX: API error {payload.get('code')}: {payload.get('msg')}")
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


CANDLES_URL = "https://www.okx.com/api/v5/market/history-candles"
OKX_BARS = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1Dutc",
            "1w": "1Wutc", "1M": "1Mutc"}
OKX_PAGE = 100  # history-candles returns at most 100 rows per request


def fetch_candles(symbol: str, quote: str, interval: str, start_ms: int, end_ms: int,
                  max_candles: int, timeout: float) -> list[Candle]:
    """Candles in [start_ms, end_ms], oldest first. Pages backwards from end_ms (`after` = older than)."""
    candles: dict[int, Candle] = {}
    cursor = end_ms + 1
    while len(candles) < max_candles:
        payload = get_json(CANDLES_URL, {"instId": f"{symbol}-{quote}", "bar": OKX_BARS[interval],
                                         "after": str(cursor), "limit": str(OKX_PAGE)}, timeout, "OKX")
        if str(payload.get("code")) != "0":
            raise ProviderError("api_error", f"OKX: API error {payload.get('code')}: {payload.get('msg')}")
        rows = payload.get("data") or []
        page = [c for c in (parse_candle_row(r) for r in rows) if c]
        for candle in page:
            if candle.time * 1000 >= start_ms:
                candles[candle.time] = candle
        if len(rows) < OKX_PAGE or not page or min(c.time for c in page) * 1000 <= start_ms:
            break
        cursor = min(c.time for c in page) * 1000
    return sorted(candles.values(), key=lambda c: c.time)[-max_candles:]
