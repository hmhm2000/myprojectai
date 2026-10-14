"""Bull Market Support Band - port of "pineScripts/Bull Market Support Band.txt" (Pine v5, © zkdev).

20-period SMA and 21-period EMA of the WEEKLY close (the script runs on timeframe 'W') drawn on any
chart, with the space between them filled. On other intervals the weekly values are placed on the
chart candles without look-ahead (a candle shows the last closed week; the current candle the
forming week). Lengths, the timeframe and the colors are settings (fixed in the original).
"""
from indicators.base import Indicator, Output, Param, register
from indicators.core import ema, sma

GROUP, COLORS = "settings", "colors"


def compute(d, p):
    n = len(d.time)
    if d.context is not None and d.context.interval != p["timeframe"]:
        sec = d.security(p["timeframe"], warmup=6 * max(p["sma_length"], p["ema_length"]))
        if sec is None or not sec.data.time:
            return {"sma": [None] * n, "ema": [None] * n}
        src = sec.data.source(p["source"])
        return {"sma": sec.map(sma(src, p["sma_length"])), "ema": sec.map(ema(src, p["ema_length"]))}
    src = d.source(p["source"])
    return {"sma": sma(src, p["sma_length"]), "ema": ema(src, p["ema_length"])}


register(Indicator(
    id="bmsb", name="Bull Market Support Band", pane="overlay",
    params=[
        Param("timeframe", "timeframe", "1w", label="Timeframe", group=GROUP),
        Param("source", "source", "close", label="Source", group=GROUP),
        Param("sma_length", "int", 20, min=1, max=500, label="SMA Length", group=GROUP),
        Param("ema_length", "int", 21, min=1, max=500, label="EMA Length", group=GROUP),
        Param("sma_color", "color", "#ff5252", label="20w SMA", group=COLORS),
        Param("ema_color", "color", "#4caf50", label="21w EMA", group=COLORS),
        Param("fill_color", "color", "#ff980040", label="Fill", group=COLORS),
    ],
    outputs=[
        Output("band", "band", color="@fill_color", between=("sma", "ema"), alert=False),
        Output("sma", color="@sma_color", width=2, label="20w SMA"),
        Output("ema", color="@ema_color", width=2, label="21w EMA"),
    ],
    compute=compute,
    warmup=lambda p: 6 * max(p["sma_length"], p["ema_length"]),   # used when the chart itself is weekly
    summary=("sma_length", "ema_length"),
    description="Bull Market Support Band (zkdev) - 20W SMA and 21W EMA",
))
