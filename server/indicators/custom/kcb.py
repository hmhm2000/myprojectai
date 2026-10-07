"""Keltner Channels Bands (KCB) - port of pineScripts/KCB.txt (Pine v4, © ceyhun).

basis = ema(src, length); bands = basis ± 1/2/3 × atr(atr_length), each pair filled (Pine fill,
default transparency 90). Differences from the original:
- `mult` was an input without effect in Pine; here it scales the bands (1.0 = original),
- the colors are parameters; the basis default is light instead of black (dark chart background).
"""
from indicators.base import Indicator, Output, Param, register
from indicators.core import atr, ema

GROUP, COLORS = "settings", "colors"

PARAMS = [
    Param("length", "int", 20, min=1, max=1000, label="Length", group=GROUP),
    Param("atr_length", "int", 10, min=1, max=1000, label="Atr Length", group=GROUP),
    Param("mult", "float", 1.0, min=0.001, max=50, label="mult", group=GROUP),
    Param("source", "source", "close", label="Source", group=GROUP),
    Param("basis_color", "color", "#e4e4e7", label="Basis", group=COLORS),
    Param("band1_color", "color", "#4caf50", label="Upper/Lower 1", group=COLORS),
    Param("band2_color", "color", "#ff5252", label="Upper/Lower 2", group=COLORS),
    Param("band3_color", "color", "#2196f3", label="Upper/Lower 3", group=COLORS),
]


def compute(d, p):
    ma = ema(d.source(p["source"]), p["length"])
    rng = atr(d.high, d.low, d.close, p["atr_length"])
    out = {"basis": ma}
    for k in (1, 2, 3):
        width = [None if a is None or m is None else k * p["mult"] * a for m, a in zip(ma, rng)]
        out[f"upper_{k}"] = [None if w is None else m + w for m, w in zip(ma, width)]
        out[f"lower_{k}"] = [None if w is None else m - w for m, w in zip(ma, width)]
    return out


register(Indicator(
    id="kcb", name="Keltner Channels Bands (KCB)", pane="overlay",
    params=PARAMS,
    outputs=[
        Output("fill_3", "band", color="@band3_color", opacity=0.1, between=("upper_3", "lower_3"), alert=False),
        Output("fill_2", "band", color="@band2_color", opacity=0.1, between=("upper_2", "lower_2"), alert=False),
        Output("fill_1", "band", color="@band1_color", opacity=0.1, between=("upper_1", "lower_1"), alert=False),
        Output("basis", color="@basis_color", label="Basis"),
        Output("upper_1", color="@band1_color", label="Upper 1"),
        Output("lower_1", color="@band1_color", label="Lower 1"),
        Output("upper_2", color="@band2_color", label="Upper 2"),
        Output("lower_2", color="@band2_color", label="Lower 2"),
        Output("upper_3", color="@band3_color", label="Upper 3"),
        Output("lower_3", color="@band3_color", label="Lower 3"),
    ],
    compute=compute,
    warmup=lambda p: max(6 * p["length"], 10 * p["atr_length"]) + 1,
    summary=("length", "atr_length"),
    description="Keltner Channels Bands (ceyhun) - EMA ± 1/2/3 ATR",
))
