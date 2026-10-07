"""Open Interest RSI (OI RSI) - port of "pineScripts/OI RSI.txt" (Pine v6, © Demech).

RSI of the open interest and of the price, each with a VWMA (weighted by the chart's volume, like
ta.vwma), signal backgrounds (buy: OI RSI > 70 and RSI < 30, or both < 30; sell: OI RSI < 30 and
RSI > 70, or both > 70), levels 20/30/47/53/70/80 with fills, and the three alert conditions.
Differences:
- open interest comes from the coin's USDT perpetual on Bybit (fallback OKX) - TradingView reads
  "<SYMBOL>_OI" of the chart's exchange; "Override symbol" takes the OI of another coin,
- the OI value of a candle is the open interest at the candle's end (the newest candle: the latest
  value published by the exchange, refreshed every minute),
- without open interest data (coin without a perpetual) the OI lines stay empty instead of the
  Pine runtime error; the price RSI still works,
- the OI RSI line is light by default (black in the original - invisible on the dark chart).
"""
from indicators.base import Indicator, Output, Param, register
from indicators.builtin import rsi_series
from indicators.core import sma

GROUP, COLORS = "settings", "colors"


def vwma(src, volume, length):
    """ta.vwma: sma(src * volume) / sma(volume)."""
    num = sma([None if s is None else s * v for s, v in zip(src, volume)], length)
    den = sma(volume, length)
    return [None if n is None or not dv else n / dv for n, dv in zip(num, den)]


def compute(d, p):
    n = len(d.time)
    oi = d.open_interest(p["symbol"] if p["override_symbol"] else None) or [None] * n
    oi_rsi = rsi_series(oi, p["oi_rsi_period"])
    rsi = rsi_series(d.close, p["rsi_period"])
    buy = [(o is not None and r is not None) and ((o > 70 and r < 30) or (o < 30 and r < 30)) for o, r in zip(oi_rsi, rsi)]
    sell = [(o is not None and r is not None) and ((o < 30 and r > 70) or (o > 70 and r > 70)) for o, r in zip(oi_rsi, rsi)]
    const = lambda v: [float(v)] * n
    return {
        "buy_background": [1.0 if b else None for b in buy],
        "sell_background": [1.0 if s else None for s in sell],
        "level_80": const(80), "level_70": const(70), "level_53": const(53),
        "level_47": const(47), "level_30": const(30), "level_20": const(20),
        "oi_rsi": oi_rsi,
        "oi_vwma": vwma(oi_rsi, d.volume, p["oi_vwma_period"]),
        "rsi": rsi,
        "rsi_vwma": vwma(rsi, d.volume, p["vwma_period"]),
        "combined": [1.0 if b or s else 0.0 for b, s in zip(buy, sell)],
        "buy": [1.0 if b else 0.0 for b in buy],
        "sell": [1.0 if s else 0.0 for s in sell],
    }


def _level(name, color, label):
    return Output(name, color=color, label=label, alert=False)


register(Indicator(
    id="oi_rsi", name="Open Interest RSI (OI RSI)", pane="separate",
    params=[
        Param("override_symbol", "bool", False, label="Override symbol", group=GROUP),
        Param("symbol", "symbol", "BTC", label="Symbol", group=GROUP),
        Param("oi_rsi_period", "int", 14, min=1, max=500, label="OI RSI Period", group=GROUP),
        Param("oi_vwma_period", "int", 14, min=1, max=500, label="OI VWMA Period", group=GROUP),
        Param("rsi_period", "int", 14, min=1, max=500, label="RSI Period", group=GROUP),
        Param("vwma_period", "int", 14, min=1, max=500, label="VWMA Period", group=GROUP),
        Param("oi_rsi_color", "color", "#e4e4e7", label="Open Interest RSI", group=COLORS),
        Param("oi_vwma_color", "color", "#ff9800", label="Open Interest VWMA", group=COLORS),
        Param("rsi_color", "color", "#2196f3", label="RSI", group=COLORS),
        Param("rsi_vwma_color", "color", "#9c27b0", label="RSI VWMA", group=COLORS),
        Param("buy_color", "color", "#4caf5080", label="Buy background", group=COLORS),
        Param("sell_color", "color", "#ff525280", label="Sell background", group=COLORS),
    ],
    outputs=[
        Output("buy_background", "background", color="@buy_color", label="Long Signal", alert=False),
        Output("sell_background", "background", color="@sell_color", label="Short Signal", alert=False),
        Output("upper_fill", "band", color="#ff5252", opacity=0.2, between=("level_80", "level_70"), alert=False),
        Output("lower_fill", "band", color="#4caf50", opacity=0.2, between=("level_30", "level_20"), alert=False),
        Output("middle_fill", "band", color="#787b86", opacity=0.2, between=("level_53", "level_47"), alert=False),
        _level("level_80", "#ff5252", "Upper Level"),
        _level("level_70", "#ff5252", "Upper Level"),
        _level("level_53", "#787b86", "upper Middl Level"),
        _level("level_47", "#787b86", "Lower Middl Level"),
        _level("level_30", "#4caf50", "Lower Level"),
        _level("level_20", "#4caf50", "Lower Level"),
        Output("oi_rsi", color="@oi_rsi_color", label="Open Interest RSI"),
        Output("oi_vwma", color="@oi_vwma_color", label="Open Interest VWMA"),
        Output("rsi", color="@rsi_color", label="RSI"),
        Output("rsi_vwma", color="@rsi_vwma_color", label="RSI VWMA"),
        Output("combined", "none", label="Combined Alert"),
        Output("buy", "none", label="buy"),
        Output("sell", "none", label="sell"),
    ],
    compute=compute,
    warmup=lambda p: 10 * max(p["oi_rsi_period"], p["rsi_period"]) + max(p["oi_vwma_period"], p["vwma_period"]),
    summary=("oi_rsi_period", "rsi_period"),
    description="Open Interest RSI (Demech) - RSI of open interest and price with VWMA and signals",
))
