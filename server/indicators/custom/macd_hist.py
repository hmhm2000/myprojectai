"""MT4 MACDHist Alert (Correct Colors) - port of pineScripts/MACDHist.txt (Pine v5).

MT4-style MACD: the histogram IS the MACD line (fast EMA - slow EMA), the signal is an SMA of it.
Column colors: >= 0 and rising -> green, >= 0 and falling -> lime, < 0 and falling -> maroon,
otherwise red (also when the value did not change), exactly like the original.
The colors are parameters (Pine v5 color.green / lime / maroon / red by default).
"""
from indicators.base import Indicator, Output, Param, register
from indicators.core import ema, sma

GROUP, COLORS = "settings", "colors"


def compute(d, p):
    fast, slow = ema(d.close, p["fast_length"]), ema(d.close, p["slow_length"])
    macd = [None if f is None or s is None else f - s for f, s in zip(fast, slow)]
    colors = []
    for i, h in enumerate(macd):
        prev = macd[i - 1] if i else None
        rising = h is not None and prev is not None and h > prev
        falling = h is not None and prev is not None and h < prev
        if h is None:
            colors.append(None)
        elif h >= 0 and rising:
            colors.append(0)
        elif h >= 0 and falling:
            colors.append(1)
        elif h < 0 and falling:
            colors.append(2)
        else:
            colors.append(3)
    return {"histogram": macd, "histogram:color": colors, "macd": macd, "signal": sma(macd, p["signal_length"])}


register(Indicator(
    id="macd_hist", name="MT4 MACD Hist", pane="separate",
    params=[
        Param("fast_length", "int", 12, min=1, max=500, label="Fast EMA", group=GROUP),
        Param("slow_length", "int", 26, min=1, max=500, label="Slow EMA", group=GROUP),
        Param("signal_length", "int", 9, min=1, max=500, label="Signal SMA", group=GROUP),
        Param("rising_up_color", "color", "#4caf50", label="hist >= 0, rising", group=COLORS),
        Param("falling_up_color", "color", "#00e676", label="hist >= 0, falling", group=COLORS),
        Param("falling_down_color", "color", "#880e4f", label="hist < 0, falling", group=COLORS),
        Param("rising_down_color", "color", "#ff5252", label="hist < 0, rising", group=COLORS),
        Param("macd_color", "color", "#4caf50", label="MACD Line", group=COLORS),
        Param("signal_color", "color", "#ff5252", label="Signal Line", group=COLORS),
    ],
    outputs=[
        Output("histogram", "histogram", palette=("@rising_up_color", "@falling_up_color", "@falling_down_color",
                                                  "@rising_down_color"), label="Histogram"),
        Output("macd", color="@macd_color", label="MACD Line"),
        Output("signal", color="@signal_color", label="Signal Line"),
    ],
    compute=compute,
    warmup=lambda p: 6 * max(p["fast_length"], p["slow_length"]) + p["signal_length"],
    summary=("fast_length", "slow_length", "signal_length"),
    description="MT4 MACDHist (Correct Colors) - histogram = MACD, signal = SMA",
))
