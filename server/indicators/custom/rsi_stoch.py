"""RSI & Stochastic RSI - port of "pineScripts/RSI and STOCH RSI.txt" (Pine v6).

RSI with an optional smoothing MA (SMA, SMA + Bollinger Bands, EMA, SMMA/RMA, WMA, VWMA), the
70/30 band with green / red fills above 70 / below 30, Stochastic RSI K / D with the 80/20 band, and
optional regular divergences (pivots 5/5 within 5-60 candles; Bull / Bear labels on the pivot,
drawn 5 candles back like the original's offset). Alerts: Regular Bullish / Bearish Divergence.
The original's gradient fills are drawn as plain translucent fills.
"""
from indicators.base import Indicator, Output, Param, register
from indicators.builtin import rsi_series
from indicators.core import (ago, barssince, ema, offset_left, pivothigh, pivotlow, rma, sma, stdev, stoch,
                             valuewhen_nth, vwma, wma)

RSI, STOCH, SMOOTH, COLORS = "rsi", "stoch", "rsi_smoothing", "colors"
MA_TYPES = ("None", "SMA", "SMA + Bollinger Bands", "EMA", "SMMA (RMA)", "WMA", "VWMA")
LEFT = RIGHT = 5
RANGE_LOWER, RANGE_UPPER = 5, 60


def _ma(kind, src, length, volume):
    return {"SMA": sma, "SMA + Bollinger Bands": sma, "EMA": ema, "SMMA (RMA)": rma, "WMA": wma}.get(
        kind, lambda s, n: vwma(s, volume, n))(src, length)


def compute(d, p):
    n = len(d.time)
    none = [None] * n
    rsi = rsi_series(d.source(p["rsi_source"]), p["rsi_length"])
    k = sma(stoch(*([rsi_series(d.source(p["stoch_source"]), p["length_rsi"])] * 3), p["length_stoch"]), p["smooth_k"])
    dd = sma(k, p["smooth_d"])
    kind = p["ma_type"]
    ma = _ma(kind, rsi, p["ma_length"], d.volume) if kind != "None" else none
    bb = [None if s is None else s * p["bb_mult"] for s in stdev(rsi, p["ma_length"])] if kind == MA_TYPES[2] else none
    const = lambda v: [float(v)] * n

    out = {
        "level_70": const(70), "level_30": const(30), "level_80": const(80), "level_20": const(20),
        "ob_top": [r if r is not None and r > 70 else None for r in rsi],
        "ob_bottom": [70.0 if r is not None and r > 70 else None for r in rsi],
        "os_top": [30.0 if r is not None and r < 30 else None for r in rsi],
        "os_bottom": [r if r is not None and r < 30 else None for r in rsi],
        "rsi": rsi, "rsi_ma": ma,
        "bb_upper": [None if m is None or b is None else m + b for m, b in zip(ma, bb)],
        "bb_lower": [None if m is None or b is None else m - b for m, b in zip(ma, bb)],
        "stoch_k": k, "stoch_d": dd,
        "bull_mark": none, "bear_mark": none, "bull_label": none, "bear_label": none,
        "bull_div": [0.0] * n, "bear_div": [0.0] * n,
    }
    if p["calculate_divergence"]:
        rsi_lbr, low_lbr, high_lbr = ago(rsi, RIGHT), ago(d.low, RIGHT), ago(d.high, RIGHT)
        pl_found = [v is not None for v in pivotlow(rsi, LEFT, RIGHT)]
        ph_found = [v is not None for v in pivothigh(rsi, LEFT, RIGHT)]

        def in_range(found):                          # _inRange(found[1])
            bars = barssince(ago(found, 1))
            return [b is not None and RANGE_LOWER <= b <= RANGE_UPPER for b in bars]

        prev_rsi_low, prev_low = valuewhen_nth(pl_found, rsi_lbr, 1), valuewhen_nth(pl_found, low_lbr, 1)
        prev_rsi_high, prev_high = valuewhen_nth(ph_found, rsi_lbr, 1), valuewhen_nth(ph_found, high_lbr, 1)
        gt = lambda a, b: a is not None and b is not None and a > b
        bull = [f and r and gt(rl, pr) and gt(pl, lo)
                for f, r, rl, pr, lo, pl in zip(pl_found, in_range(pl_found), rsi_lbr, prev_rsi_low, low_lbr, prev_low)]
        bear = [f and r and gt(pr, rl) and gt(hi, ph)
                for f, r, rl, pr, hi, ph in zip(ph_found, in_range(ph_found), rsi_lbr, prev_rsi_high, high_lbr, prev_high)]
        at = lambda cond: offset_left([v if c else None for v, c in zip(rsi_lbr, cond)], RIGHT)
        out.update({
            "bull_mark": at(bull), "bear_mark": at(bear), "bull_label": at(bull), "bear_label": at(bear),
            "bull_div": [1.0 if b else 0.0 for b in bull], "bear_div": [1.0 if b else 0.0 for b in bear],
        })
    return out


def _level(name, color, opacity=1.0):
    return Output(name, color=color, opacity=opacity, alert=False)


register(Indicator(
    id="rsi_stoch", name="RSI & Stochastic RSI", pane="separate",
    params=[
        Param("rsi_length", "int", 14, min=1, max=500, label="RSI Length", group=RSI),
        Param("rsi_source", "source", "close", label="Source", group=RSI),
        Param("calculate_divergence", "bool", False, label="Calculate Divergence", group=RSI),
        Param("smooth_k", "int", 3, min=1, max=100, label="Stoch RSI K", group=STOCH),
        Param("smooth_d", "int", 3, min=1, max=100, label="Stoch RSI D", group=STOCH),
        Param("length_rsi", "int", 14, min=1, max=500, label="Stoch RSI Length", group=STOCH),
        Param("length_stoch", "int", 14, min=1, max=500, label="Stochastic Length", group=STOCH),
        Param("stoch_source", "source", "close", label="Stoch RSI Source", group=STOCH),
        Param("ma_type", "select", "None", label="Type", group=SMOOTH, options=MA_TYPES),
        Param("ma_length", "int", 14, min=1, max=500, label="Length", group=SMOOTH),
        Param("bb_mult", "float", 2.0, min=0.001, max=50, label="BB StdDev", group=SMOOTH),
        Param("rsi_color", "color", "#7e57c2", label="RSI", group=COLORS),
        Param("ma_color", "color", "#ffeb3b", label="RSI-based MA", group=COLORS),
        Param("k_color", "color", "#2962ff", label="Stoch RSI K", group=COLORS),
        Param("d_color", "color", "#ff6d00", label="Stoch RSI D", group=COLORS),
    ],
    outputs=[
        Output("rsi_band", "band", color="#7e57c21a", between=("level_70", "level_30"), alert=False),
        Output("stoch_band", "band", color="#2196f31a", between=("level_80", "level_20"), alert=False),
        Output("ob_fill", "band", color="#4caf5066", between=("ob_top", "ob_bottom"), alert=False),
        Output("os_fill", "band", color="#ff525266", between=("os_top", "os_bottom"), alert=False),
        Output("bb_fill", "band", color="#4caf501a", between=("bb_upper", "bb_lower"), alert=False),
        _level("level_70", "#787b86"), _level("level_30", "#787b86"),
        _level("level_80", "#787b86", 0.6), _level("level_20", "#787b86", 0.6),
        Output("ob_top", "none", alert=False), Output("ob_bottom", "none", alert=False),
        Output("os_top", "none", alert=False), Output("os_bottom", "none", alert=False),
        Output("rsi", color="@rsi_color", label="RSI"),
        Output("rsi_ma", color="@ma_color", label="RSI-based MA"),
        Output("bb_upper", color="#4caf50", label="Upper Bollinger Band", alert=False),
        Output("bb_lower", color="#4caf50", label="Lower Bollinger Band", alert=False),
        Output("stoch_k", color="@k_color", label="Stoch RSI K"),
        Output("stoch_d", color="@d_color", label="Stoch RSI D"),
        Output("bull_mark", "points", color="#4caf50", radius=3, label="Regular Bullish", alert=False),
        Output("bear_mark", "points", color="#ff5252", radius=3, label="Regular Bearish", alert=False),
        Output("bull_label", "char", color="#4caf50", char="Bull", alert=False),
        Output("bear_label", "char", color="#ff5252", char="Bear", alert=False),
        Output("bull_div", "none", label="Regular Bullish Divergence"),
        Output("bear_div", "none", label="Regular Bearish Divergence"),
    ],
    compute=compute,
    warmup=lambda p: 10 * max(p["rsi_length"], p["length_rsi"]) + p["length_stoch"] + p["smooth_k"] + p["smooth_d"]
    + p["ma_length"] + RANGE_UPPER,
    summary=("rsi_length", "length_rsi", "length_stoch"),
    description="RSI & Stochastic RSI - RSI with smoothing MA / Bollinger, Stoch RSI, divergences",
))
