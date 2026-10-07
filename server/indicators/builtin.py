"""Built-in indicators, defined like their TradingView (Pine v5) counterparts."""
from indicators.base import Indicator, Output, Param, register
from indicators.core import change, combine, ema, highest, lowest, rma, sma, stdev

SOURCE = Param("source", "source", "close")


def _length(default: int) -> Param:
    return Param("length", "int", default, min=1, max=1000)


# ------------------------------------------------------------------ moving averages

register(Indicator(
    id="sma", name="SMA", pane="overlay",
    params=[_length(20), SOURCE],
    outputs=[Output("sma", color="#f59e0b")],
    compute=lambda d, p: {"sma": sma(d.source(p["source"]), p["length"])},
    warmup=lambda p: p["length"],
    description="Simple moving average (ta.sma)",
))

register(Indicator(
    id="ema", name="EMA", pane="overlay",
    params=[_length(20), SOURCE],
    outputs=[Output("ema", color="#38bdf8")],
    compute=lambda d, p: {"ema": ema(d.source(p["source"]), p["length"])},
    warmup=lambda p: p["length"] * 4,   # EMA depends on all history - 4x length makes the seed negligible
    description="Exponential moving average (ta.ema, seeded with SMA)",
))


# ------------------------------------------------------------------ RSI

def rsi_series(src, length):
    """TradingView RSI: rma of gains / losses; down == 0 -> 100, up == 0 -> 0."""
    diff = change(src)
    up = rma([None if v is None else max(v, 0.0) for v in diff], length)
    down = rma([None if v is None else max(-v, 0.0) for v in diff], length)
    out = []
    for u, dn in zip(up, down):
        if u is None or dn is None:
            out.append(None)
        elif dn == 0:
            out.append(100.0)
        elif u == 0:
            out.append(0.0)
        else:
            out.append(100 - 100 / (1 + u / dn))
    return out


register(Indicator(
    id="rsi", name="RSI", pane="separate",
    params=[_length(14), SOURCE],
    outputs=[Output("rsi", color="#a855f7")],
    compute=lambda d, p: {"rsi": rsi_series(d.source(p["source"]), p["length"])},
    warmup=lambda p: p["length"] * 10 + 1,   # rma (alpha = 1/length) converges slowly - keeps the result within ~1e-4
    levels=[30, 70],
    description="Relative Strength Index (ta.rsi)",
))


# ------------------------------------------------------------------ MACD

def _macd(d, p):
    src = d.source(p["source"])
    macd = combine(lambda a, b: a - b, ema(src, p["fast"]), ema(src, p["slow"]))
    signal = ema(macd, p["signal"])
    return {"macd": macd, "signal": signal, "histogram": combine(lambda a, b: a - b, macd, signal)}


register(Indicator(
    id="macd", name="MACD", pane="separate",
    params=[Param("fast", "int", 12, min=1, max=500), Param("slow", "int", 26, min=1, max=500),
            Param("signal", "int", 9, min=1, max=500), SOURCE],
    outputs=[Output("histogram", "histogram"), Output("macd", color="#38bdf8"), Output("signal", color="#f59e0b")],
    compute=_macd,
    warmup=lambda p: max(p["fast"], p["slow"]) * 6 + p["signal"] * 4,
    levels=[0],
    description="MACD (ta.macd: EMA fast - EMA slow, signal = EMA of MACD)",
))


# ------------------------------------------------------------------ Bollinger Bands

def _bb(d, p):
    src = d.source(p["source"])
    basis = sma(src, p["length"])
    dev = stdev(src, p["length"])
    mult = p["mult"]
    return {
        "basis": basis,
        "upper": combine(lambda b, s: b + mult * s, basis, dev),
        "lower": combine(lambda b, s: b - mult * s, basis, dev),
    }


register(Indicator(
    id="bb", name="Bollinger Bands", pane="overlay",
    params=[_length(20), Param("mult", "float", 2.0, min=0.001, max=50), SOURCE],
    outputs=[Output("basis", color="#f59e0b"), Output("upper", color="#38bdf8"), Output("lower", color="#38bdf8")],
    compute=_bb,
    warmup=lambda p: p["length"],
    description="Bollinger Bands (SMA ± mult × population stdev)",
))


# ------------------------------------------------------------------ Stochastic

def _stoch(d, p):
    hi = highest(d.high, p["k_length"])
    lo = lowest(d.low, p["k_length"])
    raw = [None if h is None or l is None or h == l else 100 * (c - l) / (h - l)
           for c, h, l in zip(d.close, hi, lo)]
    k = sma(raw, p["k_smoothing"])
    return {"k": k, "d": sma(k, p["d_smoothing"])}


register(Indicator(
    id="stoch", name="Stochastic", pane="separate",
    params=[Param("k_length", "int", 14, min=1, max=500), Param("k_smoothing", "int", 1, min=1, max=100),
            Param("d_smoothing", "int", 3, min=1, max=100)],
    outputs=[Output("k", color="#38bdf8"), Output("d", color="#f59e0b")],
    compute=_stoch,
    warmup=lambda p: p["k_length"] + p["k_smoothing"] + p["d_smoothing"],
    levels=[20, 80],
    description="Stochastic %K / %D (ta.stoch, TradingView defaults 14 / 1 / 3)",
))

