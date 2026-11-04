"""Harmonic patterns - port of "pineScripts/Harmonics.txt" (Pine v5, © reees).

The script keeps its logic in the author's libraries (reees/TA, Pattern, Obj_XABCD_Harmonic), which are
not part of the file, so what lives there is written from the standard definitions: the ratios (RATIOS),
the pivots and the three parts of the score. The rest follows the script: XABC from pivots of lengths
3-20, a leg's ratio may miss by `pct_err` %, a leg's length may differ from the others by `pct_asym` %,
D is a pivot confirmed by `confirm` bars that goes past everything since C, a deeper valid D with a
score not lower replaces the old one, and a pattern dies when price passes C or the far end of the PRZ.
Left out: the entry after point C and the statistics table.

Patterns are shapes, not values per candle: compute returns them under "drawings" (see Indicator) and
the chart draws them on one canvas layer. Only closed candles are read, so a result can be reused until
the next candle closes - the chart asks every few seconds for the newest candles.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from indicators.base import Indicator, Output, Param, register
from services.intervals import parse

SHOW, TYPES, TARGETS, TRADE, PATTERN, STYLE = "harmonics_show", "harmonics_types", "harmonics_targets", \
    "harmonics_trade", "harmonics_pattern", "style"
T1_OPTIONS = (".382 AD", ".5 AD", ".618 AD", ".382 XA", ".5 XA", ".618 XA", "1.272 XA", "1.618 XA",
              ".382 CD", ".5 CD", ".618 CD", "1.272 CD", "1.618 CD", "A", "B", "C")
T2_OPTIONS = ("None", ".618 AD", "1.272 AD", "1.618 AD", ".618 XA", "1.272 XA", "1.618 XA",
              ".618 CD", "1.272 CD", "1.618 CD", "A", "B", "C")
BARS_BEFORE_D = 3                       # D must be the extreme of at least this many bars before it
CACHE_SIZE = 32
_cache: OrderedDict = OrderedDict()


@dataclass(frozen=True)
class Ratios:
    ab: Optional[tuple]                 # AB / XA (Shark: not used)
    bc: tuple                           # BC / AB
    cd: Optional[tuple]                 # CD / BC (Cypher: not used)
    ad: tuple                           # AD / XA (Cypher: CD / XC)


BC = (.382, .886)
RATIOS = {
    "gartley": Ratios((.618, .618), BC, (1.13, 1.618), (.786, .786)),
    "bat": Ratios((.382, .5), BC, (1.618, 2.618), (.886, .886)),
    "butterfly": Ratios((.786, .786), BC, (1.618, 2.24), (1.27, 1.618)),
    "crab": Ratios((.382, .618), BC, (2.24, 3.618), (1.618, 1.618)),
    "shark": Ratios(None, (1.13, 1.618), (1.618, 2.24), (.886, 1.13)),
    "cypher": Ratios((.382, .618), (1.13, 1.414), None, (.786, .786)),
}
DEFAULT_TARGETS = {"gartley": (".618 AD", "1.272 AD"), "bat": (".618 AD", "1.272 AD"),
                   "butterfly": (".618 AD", "1.272 AD"), "crab": (".618 AD", "1.618 AD"),
                   "shark": (".382 AD", "C"), "cypher": (".618 CD", "1.618 XA")}


def _error(value: float, band: tuple) -> float:
    """How far (share of the ratio) a value is from the band of a harmonic ratio; 0 inside it."""
    low, high = band
    if low <= value <= high:
        return 0.0
    return min(abs(value - low) / low, abs(value - high) / high)


def _reach(values: list[float], sign: int, limit: int) -> list[int]:
    """For every bar: the largest n <= limit for which it is a pivot of length n (the extreme of n bars
    on both sides) - one pass for all pivot lengths. `sign` 1: highs, -1: lows."""
    size, out = len(values), []
    for i, value in enumerate(values):
        n = 0
        for k in range(1, limit + 1):
            if i - k < 0 or i + k >= size or sign * values[i - k] > sign * value or sign * values[i + k] >= sign * value:
                break
            n = k
        out.append(n)
    return out


def _zigzag(high, low, high_reach, low_reach, length: int) -> list[tuple]:
    """Pivots of this length as (bar, price, is_high), alternating; of two in a row the extreme one stays."""
    points: list[tuple] = []
    for i in range(len(high)):
        for is_high, reach, price in ((True, high_reach, high), (False, low_reach, low)):
            if reach[i] < length:
                continue
            if points and points[-1][2] == is_high:
                if (price[i] > points[-1][1]) == is_high:
                    points[-1] = (i, price[i], is_high)
            else:
                points.append((i, price[i], is_high))
    return points


def _symmetric(legs: list[int], pct: float) -> bool:
    """Every leg's length within `pct` % of the average of the other legs."""
    for i, leg in enumerate(legs):
        others = (sum(legs) - leg) / (len(legs) - 1)
        if others and abs(leg - others) / others * 100 > pct:
            return False
    return True


def _gap(first: tuple, second: tuple) -> float:
    """Distance between two price ranges; 0 when they overlap."""
    return max(0.0, min(first) - max(second), min(second) - max(first))


def _levels(kind: str, sign: int, x: float, a: float, b: float, c: float) -> tuple:
    """PRZ of a pattern: the range of D from XA and the range from BC (None for a Cypher)."""
    ratios = RATIOS[kind]
    if ratios.cd is None:
        span = abs(x - c)
        return tuple(c - sign * r * span for r in ratios.ad), None
    return (tuple(a - sign * r * abs(x - a) for r in ratios.ad),
            tuple(c - sign * r * abs(b - c) for r in ratios.cd))


def _score(errors: list[float], from_xa: tuple, from_bc: Optional[tuple], xa: float, d: Optional[float], p: dict) -> float:
    """0-100: retracement accuracy, confluence of the PRZ levels, confluence of D with them (by weights)."""
    parts = [(p["weight_err"], 1 - sum(errors) / len(errors))]
    if from_bc is not None:
        parts.append((p["weight_prz"], 1 - min(1.0, _gap(from_xa, from_bc) / xa)))
    if d is not None:
        distance = min(_gap((d, d), levels) for levels in (from_xa, from_bc) if levels is not None)
        parts.append((p["weight_d"], 1 - min(1.0, distance / xa)))
    total = sum(weight for weight, _ in parts)
    return sum(weight * value for weight, value in parts) / total * 100 if total else 0.0


def _target(option: str, sign: int, x: float, a: float, b: float, c: float, d: float) -> Optional[float]:
    """Price of a target option: a point, or a share of a leg measured from D towards the reversal."""
    if option == "None":
        return None
    if option in ("A", "B", "C"):
        return {"A": a, "B": b, "C": c}[option]
    ratio, leg = option.split()
    return d + sign * float(ratio) * {"AD": abs(a - d), "XA": abs(x - a), "CD": abs(c - d)}[leg]


def _trade(d, p: dict, sign: int, points: list, kind: str, confirmed: int, size: int) -> dict:
    """Follows the pattern after D: entry within the window, then stop / target 1 / target 2 up to the
    time limit. On a candle reaching both the stop counts - a candle doesn't tell which came first."""
    (x_bar, x), (_, a), (_, b), (_, c), (d_bar, d_price) = points
    t1 = _target(p[f"{kind}_t1"], sign, x, a, b, c, d_price)
    t2 = _target(p[f"{kind}_t2"], sign, x, a, b, c, d_price)
    length = d_bar - x_bar
    entry_end = d_bar + int(length * p["entry_window"])
    time_end = d_bar + int(length * p["time_limit"])
    limit = d_price * (1 + sign * p["entry_pct"] / 100)
    out = {"t1": t1, "t2": t2, "entry": None, "stop": None, "status": "missed", "until": min(entry_end, size - 1)}
    if sign * (t1 - limit) <= 0:                    # the target is already behind the entry
        return out
    entry_bar = next((k for k in range(confirmed, min(entry_end, size - 1) + 1)
                      if sign * (limit - (d.low[k] if sign > 0 else d.high[k])) >= 0), None)
    if entry_bar is None:
        if entry_end >= size:
            out.update(status="waiting", until=size - 1)
        return out
    entry = min(limit, d.open[entry_bar]) if sign > 0 else max(limit, d.open[entry_bar])
    stop = entry - sign * abs(t1 - entry) * p["stop_pct"] / 100
    out.update(entry=entry, stop=stop)
    first_hit = False
    for k in range(entry_bar, min(time_end, size - 1) + 1):
        worst, best = (d.low[k], d.high[k]) if sign > 0 else (d.high[k], d.low[k])
        if not first_hit and sign * (stop - worst) >= 0:
            out.update(status="failed", until=k)
            return out
        if not first_hit and sign * (best - t1) >= 0:
            first_hit = True
        if first_hit and (t2 is None or sign * (best - t2) >= 0):
            out.update(status="target1" if t2 is None else "target2", until=k)
            return out
    if time_end >= size:
        out.update(status="target1_open" if first_hit else "open", until=size - 1)
    else:
        out.update(status="target1" if first_hit else "timeout", until=time_end)
    return out


def _find_d(d, p: dict, kind: str, sign: int, points: list, errors: list, size: int):
    """Point D of an XABC: (bar, price, score, bar it was first confirmed on) - or None, plus whether the
    pattern can still complete (it is potential) at the end of the candles."""
    (x_bar, x), (a_bar, a), (b_bar, b), (c_bar, c) = points
    ratios = RATIOS[kind]
    allowed = p["pct_err"] / 100
    from_xa, from_bc = _levels(kind, sign, x, a, b, c)
    xa, bc, xc = abs(x - a), abs(b - c), abs(x - c)
    far = min(*from_xa, *(from_bc or from_xa)) if sign > 0 else max(*from_xa, *(from_bc or from_xa))
    far -= sign * xa * allowed
    limit = c_bar + int((c_bar - x_bar) / 3 * (1 + p["pct_asym"] / 100))
    near, away = (d.low, d.high) if sign > 0 else (d.high, d.low)
    extreme = None                                  # how far CD has gone so far
    best, first = None, None
    alive = True
    for bar in range(c_bar + 1, min(limit, size - 1 - p["confirm"]) + 1):
        if sign * (away[bar] - c) > 0 or sign * (far - near[bar]) > 0:
            alive = False
            break
        price = near[bar]
        deeper = extreme is None or sign * (extreme - price) >= 0
        extreme = price if deeper else extreme
        if not deeper or bar - BARS_BEFORE_D < 0:
            continue
        if any(sign * (near[bar] - near[bar - k]) > 0 for k in range(1, BARS_BEFORE_D + 1)):
            continue
        if any(sign * (near[bar] - near[bar + k]) > 0 for k in range(1, p["confirm"] + 1)):
            continue
        legs = [a_bar - x_bar, b_bar - a_bar, c_bar - b_bar, bar - c_bar]
        if not _symmetric(legs, p["pct_asym"]):
            continue
        cd = abs(c - price)
        last = [_error(cd / xc if ratios.cd is None else abs(a - price) / xa, ratios.ad)]
        if ratios.cd is not None:
            last.append(_error(cd / bc, ratios.cd))
        if max(last) > allowed:
            continue
        score = _score(errors + last, from_xa, from_bc, xa, price, p)
        if first is None:
            first = bar + p["confirm"]
        if best is None or score >= best[2]:
            best = (bar, price, score)
    open_end = alive and limit >= size - 1 - p["confirm"]
    return (*best, first) if best else None, open_end


def _detect(d, p: dict, size: int) -> tuple:
    """Patterns on the first `size` candles: (completed {(side, D bar): pattern}, potential ones)."""
    high, low = d.high[:size], d.low[:size]
    high_reach = _reach(high, 1, p["pivot_max"])
    low_reach = _reach(low, -1, p["pivot_max"])
    kinds = [k for k in RATIOS if p[k]]
    allowed = p["pct_err"] / 100
    done, potential, seen = {}, {}, set()
    for length in range(p["pivot_min"], p["pivot_max"] + 1):
        pivots = _zigzag(high, low, high_reach, low_reach, length)
        for i in range(len(pivots) - 3):
            quad = pivots[i:i + 4]
            key = tuple(q[0] for q in quad)
            if key in seen:
                continue
            seen.add(key)
            (x_bar, x, x_high), (a_bar, a, _), (b_bar, b, _), (c_bar, c, _) = quad
            sign = -1 if x_high else 1              # 1: bullish (X low, D low)
            if not _symmetric([a_bar - x_bar, b_bar - a_bar, c_bar - b_bar], p["pct_asym"]):
                continue
            ab, bc = abs(a - b) / abs(x - a), abs(c - b) / abs(a - b)
            points = [(x_bar, x), (a_bar, a), (b_bar, b), (c_bar, c)]
            for kind in kinds:
                ratios = RATIOS[kind]
                errors = [_error(bc, ratios.bc)] + ([_error(ab, ratios.ab)] if ratios.ab else [])
                if max(errors) > allowed:
                    continue
                found, open_end = _find_d(d, p, kind, sign, points, errors, size)
                if found:
                    bar, price, score, first = found
                    best = done.get((sign, bar))
                    if score >= p["min_score"] and (best is None or score > best["score"]):
                        done[(sign, bar)] = {"kind": kind, "sign": sign, "score": score, "first": first,
                                             "points": [*points, (bar, price)]}
                elif open_end and p["show_potential"]:
                    from_xa, from_bc = _levels(kind, sign, x, a, b, c)
                    score = _score(errors, from_xa, from_bc, abs(x - a), None, p)
                    best = potential.get((sign, c_bar))
                    if score >= p["min_score"] and (best is None or score > best["score"]):
                        potential[(sign, c_bar)] = {"kind": kind, "sign": sign, "score": score, "points": points}
    return done, potential


def _drawing(d, pattern: dict, status: str, until: int, **extra) -> dict:
    points = pattern["points"]
    x, a, b, c = (point[1] for point in points[:4])
    from_xa, from_bc = _levels(pattern["kind"], pattern["sign"], x, a, b, c)
    prz = (*from_xa, *(from_bc or ()))
    bars = "_".join(str(d.time[point[0]]) for point in points)
    return {"id": f'{pattern["kind"]}_{bars}', "kind": pattern["kind"], "bull": pattern["sign"] > 0,
            "score": round(pattern["score"], 1), "points": [[d.time[bar], price] for bar, price in points],
            "prz": [min(prz), max(prz)], "status": status, "until": d.time[until], **extra}


def _closed(d) -> int:
    """Number of closed candles (the newest one may still be forming)."""
    context = d.context
    if context is None or not d.time:
        return len(d.time)
    return len(d.time) - (parse(context.interval).next_start(d.time[-1]) > context.now)


def _compute(d, p: dict, size: int) -> dict:
    done, potential = _detect(d, p, size)
    drawings, bull, bear = [], [0.0] * len(d.time), [0.0] * len(d.time)
    for pattern in done.values():
        trade = _trade(d, p, pattern["sign"], pattern["points"], pattern["kind"], pattern["first"], size)
        status, until = trade.pop("status"), trade.pop("until")
        drawings.append(_drawing(d, pattern, status, until, **trade))
        (bull if pattern["sign"] > 0 else bear)[pattern["first"]] = 1.0
    drawings += [_drawing(d, pattern, "potential", size - 1) for pattern in potential.values()]
    return {"drawings": sorted(drawings, key=lambda item: item["points"][-1][0]),
            "bull_pattern": bull, "bear_pattern": bear}


def compute(d, p):
    size = _closed(d)
    if size < BARS_BEFORE_D + 1:
        return {"drawings": [], "bull_pattern": [0.0] * len(d.time), "bear_pattern": [0.0] * len(d.time)}
    context = d.context
    if context is None:
        return _compute(d, p, size)
    key = (context.symbol, context.interval, d.time[0], d.time[size - 1], len(d.time), tuple(sorted(p.items())))
    if key not in _cache:
        _cache[key] = _compute(d, p, size)
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    _cache.move_to_end(key)
    return dict(_cache[key])


def _type_params():
    for kind, (t1, t2) in DEFAULT_TARGETS.items():
        yield Param(kind, "bool", True, label=kind.capitalize(), group=TYPES)


def _target_params():
    for kind, (t1, t2) in DEFAULT_TARGETS.items():
        yield Param(f"{kind}_t1", "select", t1, label=f"{kind.capitalize()} target 1", group=TARGETS, options=T1_OPTIONS)
        yield Param(f"{kind}_t2", "select", t2, label=f"{kind.capitalize()} target 2", group=TARGETS, options=T2_OPTIONS)


register(Indicator(
    id="harmonics", name="Harmonics", pane="overlay",
    params=[
        Param("max_patterns", "int", 2, min=1, max=50, label="Patterns in view (per side)", group=SHOW),
        Param("min_score", "float", 90, min=0, max=100, label="Only high scoring", group=SHOW),
        Param("only_active", "bool", False, label="Only patterns in progress", group=SHOW),
        Param("show_potential", "bool", False, label="Potential/Incomplete", group=SHOW),
        Param("show_levels", "bool", True, label="Entry, stop and targets of patterns in progress", group=SHOW),
        Param("show_labels", "bool", True, label="Pattern name and score", group=SHOW),
        Param("show_points", "bool", True, label="Points X A B C D", group=SHOW),
        Param("show_ratios", "bool", False, label="Ratios of the legs", group=SHOW),
        *_type_params(),
        *_target_params(),
        Param("entry_pct", "float", 1.0, min=0, max=50, label="Enter at limit % away from D", group=TRADE),
        Param("entry_window", "float", .5, min=0, max=10, label="Entry window (time limit)", group=TRADE),
        Param("stop_pct", "float", 75, min=0, max=500, label="Stop: % of distance to target 1, beyond entry", group=TRADE),
        Param("time_limit", "float", 3, min=.1, max=20, label="Pattern time limit", group=TRADE),
        Param("pct_err", "float", 15, min=0, max=50, label="Allowed fib ratio error %", group=PATTERN),
        Param("pct_asym", "float", 250, min=0, max=1000, label="Allowed leg length asymmetry %", group=PATTERN),
        Param("confirm", "int", 1, min=1, max=20, label="Pattern validation length (# trailing bars)", group=PATTERN),
        Param("pivot_min", "int", 3, min=1, max=50, label="Shortest pivot", group=PATTERN),
        Param("pivot_max", "int", 20, min=1, max=50, label="Longest pivot", group=PATTERN),
        Param("lookback", "int", 500, min=100, max=3000, label="Lookback bars", group=PATTERN),
        Param("weight_err", "float", 4, min=0, max=20, label="Weight of retracement accuracy", group=PATTERN),
        Param("weight_prz", "float", 2, min=0, max=20, label="Weight of PRZ level confluence", group=PATTERN),
        Param("weight_d", "float", 3, min=0, max=20, label="Weight of point D / PRZ level confluence", group=PATTERN),
        Param("bull_color", "color", "#22c55e", label="Bullish lines", group=STYLE),
        Param("bear_color", "color", "#ef4444", label="Bearish lines", group=STYLE),
    ],
    outputs=[
        Output("bull", "harmonic", color="@bull_color", width=2, label="Bullish", alert=False),
        Output("bear", "harmonic", color="@bear_color", width=2, label="Bearish", alert=False),
        Output("bull_pattern", "none", label="Bullish pattern formed"),
        Output("bear_pattern", "none", label="Bearish pattern formed"),
    ],
    compute=compute,
    warmup=lambda p: p["lookback"],
    summary=("max_patterns", "min_score"),
    description="Formacje harmoniczne XABCD: Gartley, Bat, Butterfly, Crab, Shark i Cypher, ze strefą PRZ, wejściem, "
                "stopem i celami. Domyślnie tylko najlepsze i najnowsze, żeby wykres był czytelny.",
))
