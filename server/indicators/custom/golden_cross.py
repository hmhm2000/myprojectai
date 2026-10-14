"""Golden Cross - port of "pineScripts/Golden Cross.txt" (Pine v1).

Fast EMA (13) and slow EMA (49) with a mark at every cross of the two (Pine `cross`, both directions)
drawn at the fast EMA. Besides "any cross" the alerts can also use the direction (up = golden,
down = death cross), which the original did not separate.
"""
from indicators.base import Indicator, Output, Param, register
from indicators.core import crossover, crossunder, ema

GROUP, COLORS = "settings", "colors"


def compute(d, p):
    fast = ema(d.source(p["fast_source"]), p["fast_length"])
    slow = ema(d.source(p["slow_source"]), p["slow_length"])
    up, down = crossover(fast, slow), crossunder(fast, slow)
    crossed = [a or b for a, b in zip(up, down)]
    flag = lambda values: [1.0 if v else 0.0 for v in values]
    return {
        "fast": fast, "slow": slow,
        "cross_mark": [f if c else None for f, c in zip(fast, crossed)],
        "cross": flag(crossed), "cross_up": flag(up), "cross_down": flag(down),
    }


register(Indicator(
    id="golden_cross", name="Golden Cross", pane="overlay",
    params=[
        Param("fast_source", "source", "close", label="Fast MA Source", group=GROUP),
        Param("fast_length", "int", 13, min=1, max=1000, label="Fast MA Period", group=GROUP),
        Param("slow_source", "source", "close", label="Slow MA Source", group=GROUP),
        Param("slow_length", "int", 49, min=1, max=1000, label="Slow MA Period", group=GROUP),
        Param("fast_color", "color", "#ff0000", label="Fast MA", group=COLORS),
        Param("slow_color", "color", "#ffff00", label="Slow MA", group=COLORS),
        Param("cross_color", "color", "#ffff00", label="Cross", group=COLORS),
    ],
    outputs=[
        Output("fast", color="@fast_color", width=2, label="Fast MA"),
        Output("slow", color="@slow_color", width=2, label="Slow MA"),
        Output("cross_mark", "points", color="@cross_color", radius=5, label="Cross", alert=False),
        Output("cross", "none", label="Cross"),
        Output("cross_up", "none", label="Golden cross (up)"),
        Output("cross_down", "none", label="Death cross (down)"),
    ],
    compute=compute,
    warmup=lambda p: 6 * max(p["fast_length"], p["slow_length"]),
    summary=("fast_length", "slow_length"),
    description="Golden Cross - EMA 13 / EMA 49 with cross marks",
))
