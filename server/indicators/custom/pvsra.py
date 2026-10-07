"""PVSRA Candles Auto Override (PVSRA Auto) - port of "pineScripts/PVSRA Auto.txt" (Pine v5,
© TradeTravelChill, credits @creengrack).

Vector candles: volume >= 200% of the average of the 10 previous candles, or spread x volume >= the
highest of the 10 previous -> "peak" (200); volume >= 150% -> "rising" (150). Bull / bear by close vs
open. The volume columns and (optionally) the price candles get the PVSRA colors; alert conditions
as in the original.
Differences:
- "Use the volume of the equivalent perpetual": the coin's USDT perpetual on Bybit (fallback OKX)
  instead of BINANCE ...USDT.P; without one (or where a candle is missing) the chart's own candles are
  used, like the original's fallback,
- "Force override symbol" takes the perpetual of the given coin (e.g. BTC) instead of a TradingView ticker.
"""
from indicators.base import Indicator, Output, Param, register
from indicators.core import ago, highest, sma

OVERRIDE, CANDLES = "override", "candle_colors"


def compute(d, p):
    n = len(d.time)
    perp = None
    if p["override_symbol"]:
        perp = d.perp(p["symbol"])
    elif p["use_perp_volume"]:
        perp = d.perp()
    own = [d.volume, d.high, d.low, d.close, d.open]
    if perp is None:
        volume, high, low, close, open_ = own
    else:
        theirs = [perp.volume, perp.high, perp.low, perp.close, perp.open]
        # per candle: the perpetual's values, the chart's own where the perpetual has no candle
        use_own = [perp.volume[i] is None for i in range(n)]
        volume, high, low, close, open_ = (
            [o[i] if use_own[i] else t[i] for i in range(n)] for o, t in zip(own, theirs))

    average = sma(ago(volume, 1), 10)
    weighted = [v * (h - lo) for v, h, lo in zip(volume, high, low)]
    highest_weighted = highest(ago(weighted, 1), 10)
    va = []
    for v, avg, w, hw in zip(volume, average, weighted, highest_weighted):
        if (avg is not None and v >= avg * 2) or (hw is not None and w >= hw):
            va.append(200)
        elif avg is not None and v >= avg * 1.5:
            va.append(150)
        else:
            va.append(0)
    bull = [c > o for c, o in zip(close, open_)]
    # palette: 0 bull 200, 1 bear 200, 2 bull 150, 3 bear 150, 4 bull normal, 5 bear normal
    color = [(0 if a == 200 else 2 if a == 150 else 4) + (0 if b else 1) for a, b in zip(va, bull)]
    flag = lambda values: [1.0 if x else 0.0 for x in values]
    return {
        "volume": volume,
        "volume:color": color,
        "candles": [1.0] * n if p["candle_colors"] else [None] * n,
        "candles:color": color,
        "vector": flag(a > 0 for a in va),
        "peak": flag(a == 200 for a in va),
        "rising": flag(a == 150 for a in va),
        "peak_bear": flag(a == 200 and not b for a, b in zip(va, bull)),
        "peak_bull": flag(a == 200 and b for a, b in zip(va, bull)),
        "rising_bear": flag(a == 150 and not b for a, b in zip(va, bull)),
        "rising_bull": flag(a == 150 and b for a, b in zip(va, bull)),
    }


PALETTE = ("@bull_200_color", "@bear_200_color", "@bull_150_color", "@bear_150_color",
           "@bull_norm_color", "@bear_norm_color")

register(Indicator(
    id="pvsra", name="PVSRA Candles Auto", pane="separate",
    params=[
        Param("use_perp_volume", "bool", True, label="Use Vol of the equivalent BINANCE PERP Chart (If Available)",
              group=OVERRIDE),
        Param("override_symbol", "bool", False, label="Force Overide Symbol", group=OVERRIDE),
        Param("symbol", "symbol", "BTC", label="Symbol", group=OVERRIDE),
        Param("candle_colors", "bool", True, label="Set PVSRA candle colours on chart", group=CANDLES),
        Param("bull_200_color", "color", "#00e676", label="200% Volume (bull)", group=CANDLES),
        Param("bear_200_color", "color", "#ff5252", label="200% Volume (bear)", group=CANDLES),
        Param("bull_150_color", "color", "#2196f3", label="150% Volume (bull)", group=CANDLES),
        Param("bear_150_color", "color", "#e040fb", label="150% Volume (bear)", group=CANDLES),
        Param("bull_norm_color", "color", "#ffffff", label="Norm Volume (bull)", group=CANDLES),
        Param("bear_norm_color", "color", "#787b86", label="Norm Volume (bear)", group=CANDLES),
    ],
    outputs=[
        Output("volume", "histogram", palette=PALETTE, label="Volume"),
        Output("candles", "barcolor", palette=PALETTE, label="PVSRA candles", alert=False),
        Output("vector", "none", label="Any Vector Candle"),
        Output("peak", "none", label="Any Volume Peak(200%) Vector Candle"),
        Output("rising", "none", label="Any Volume Rising(150%) Vector Candle"),
        Output("peak_bear", "none", label="Volume Peak(200%) Bearish Vector Candle"),
        Output("peak_bull", "none", label="Volume Peak(200%) Bullish Vector Candle"),
        Output("rising_bear", "none", label="Volume Rising(150%) Bearish Vector Candle"),
        Output("rising_bull", "none", label="Volume Rising(150%) Bullish Vector Candle"),
    ],
    compute=compute,
    warmup=lambda p: 12,
    summary=(),
    description="PVSRA vector candles (TradeTravelChill) - volume 150% / 200% of the 10-candle average",
))
