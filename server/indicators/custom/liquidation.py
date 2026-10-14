"""Liquidation Longs/Shorts [UAlgo] - port of "pineScripts/Liquidation Alert.txt" (Pine v5, © UAlgo).

Distance (%) of the price from the average of SMA(15) and EMA(30), drawn as columns (red above 0,
green below). A short-liquidation circle marks a candle whose distance is the highest of the last 89
and above 0, a long-liquidation circle the lowest of the last 89 below 0 (Pine `var` state kept the
same way). Alerts: Short / Long Liquidation.
"""
from indicators.base import Indicator, Output, Param, register
from indicators.core import ema, highest, lowest, sma

CALC, STYLE = "liquidation", "style"
SOURCES = {"Close": "close", "High": "high", "Low": "low", "Open": "open"}
WINDOW = 89


def compute(d, p):
    src = d.source(SOURCES[p["source"]])
    ma1, ma2 = sma(src, p["length1"]), ema(src, p["length2"])
    dist = [None if a is None or b is None or (a + b) == 0 else (s - (a + b) / 2) / ((a + b) / 2) * 100
            for s, a, b in zip(src, ma1, ma2)]
    ph, pl = highest(dist, WINDOW), lowest(dist, WINDOW)
    last_high = last_low = None
    short_liq, long_liq = [], []
    for v, h, lo in zip(dist, ph, pl):
        if v is not None and h is not None and h == v and h > 0:
            last_high = v
        if v is not None and lo is not None and lo == v and lo < 0:
            last_low = v
        short_liq.append(v is not None and last_high is not None and last_high == v and v > 0)
        long_liq.append(v is not None and last_low is not None and last_low == v and v < 0)
    return {
        "distance": dist,
        "distance:color": [None if v is None else 1 if v > 0 else 0 for v in dist],
        "short_mark": [v if s else None for v, s in zip(dist, short_liq)],
        "long_mark": [v if lg else None for v, lg in zip(dist, long_liq)],
        "short_liq": [1.0 if s else 0.0 for s in short_liq],
        "long_liq": [1.0 if lg else 0.0 for lg in long_liq],
    }


register(Indicator(
    id="liquidation", name="Liquidation Longs/Shorts [UAlgo]", pane="separate",
    params=[
        Param("source", "select", "Close", label="Source", group=CALC, options=tuple(SOURCES)),
        Param("length1", "int", 15, min=1, max=500, label="Length 1", group=CALC),
        Param("length2", "int", 30, min=1, max=500, label="Length 2", group=CALC),
        Param("long_color", "color", "#08998180", label="Long Liquidation Color", group=STYLE),
        Param("short_color", "color", "#ff525280", label="Short Liquidation Color", group=STYLE),
        Param("long_shape_color", "color", "#00bcd4b3", label="Long Liquidation Shape Color", group=STYLE),
        Param("short_shape_color", "color", "#ff9800b3", label="Short Liquidation Shape Color", group=STYLE),
    ],
    outputs=[
        Output("distance", "histogram", palette=("@long_color", "@short_color"), label="Distance %"),
        Output("short_mark", "points", color="@short_shape_color", radius=3, label="Short liquidation", alert=False),
        Output("long_mark", "points", color="@long_shape_color", radius=3, label="Long liquidation", alert=False),
        Output("short_liq", "none", label="Short Liquidation"),
        Output("long_liq", "none", label="Long Liquidation"),
    ],
    compute=compute,
    warmup=lambda p: WINDOW + 6 * max(p["length1"], p["length2"]),
    summary=("length1", "length2"),
    description="Liquidation Longs/Shorts (UAlgo) - distance from the SMA/EMA average and 89-candle extremes",
))
