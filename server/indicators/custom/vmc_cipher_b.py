"""VuManChu Cipher B + Divergences - port of "pineScripts/VuManChu Cpiber B and Divergences.txt" (Pine v4).

Every input of the original is a parameter here (same defaults, same groups). Pine semantics kept:
- ema/sma/rsi as in Pine (indicators.core), division by zero -> na, comparisons with na are false,
- divergences: 5-candle fractals on the series, `valuewhen(...)[2]` for the previous fractal,
  plotted with offset -2 (the fractal top is drawn on its candle, 2 candles before it is confirmed),
- Schaff Trend Cycle with Pine's nz(...) recursion.
Differences:
- other timeframes (Sommi flag wave 12h, Sommi diamond Heikin-Ashi 1h/4h) are taken WITHOUT look-ahead:
  a candle uses the last CLOSED higher-timeframe candle (the Pine script asks for lookahead_on for the
  diamond, which on history uses the future close of the higher candle),
- the higher-timeframe WaveTrend is computed entirely on the higher-timeframe candles,
- "MACD Colors" and "Dark mode" are kept as settings, but - as in the original, where the MACD colors
  are computed and never plotted - they do not change the chart (the app is always dark),
- "RSI Oversold/Overbought" had swapped min/max limits in Pine (minval 50 for a default of 30); here 0-100.
Colors (Pine color.new(c, transp)) are "#rrggbbaa" parameters.
"""
import math

from indicators.base import Indicator, Output, Param, register
from indicators.builtin import rsi_series
from indicators.core import ago, cross, crossover, crossunder, ema, highest, lowest, offset_left, sma, stoch, truthy, valuewhen

WT, MFI, RSI, STOCH, SCHAFF, SOMMI, MACD, MODE, COLORS = (
    "wavetrend", "mfi", "rsi", "stoch", "schaff", "sommi", "macd", "mode", "colors")


def _p(name, type_, default, label, group, **limits):
    return Param(name, type_, default, label=label, group=group, **limits)


def _int(name, default, label, group, lo=-1000, hi=1000):
    return _p(name, "int", default, label, group, min=lo, max=hi)


PARAMS = [
    # WaveTrend
    _p("wt_show", "bool", True, "Show WaveTrend", WT),
    _p("wt_buy_show", "bool", True, "Show Buy dots", WT),
    _p("wt_gold_show", "bool", True, "Show Gold dots", WT),
    _p("wt_sell_show", "bool", True, "Show Sell dots", WT),
    _p("wt_div_show", "bool", True, "Show Div. dots", WT),
    _p("vwap_show", "bool", True, "Show Fast WT", WT),
    _int("wt_channel_len", 9, "WT Channel Length", WT, 1, 500),
    _int("wt_average_len", 12, "WT Average Length", WT, 1, 500),
    _p("wt_ma_source", "source", "hlc3", "WT MA Source", WT),
    _int("wt_ma_len", 3, "WT MA Length", WT, 1, 500),
    _int("ob_level", 53, "WT Overbought Level 1", WT),
    _int("ob_level2", 60, "WT Overbought Level 2", WT),
    _int("ob_level3", 100, "WT Overbought Level 3", WT),
    _int("os_level", -53, "WT Oversold Level 1", WT),
    _int("os_level2", -60, "WT Oversold Level 2", WT),
    _int("os_level3", -75, "WT Oversold Level 3", WT),
    _p("wt_show_div", "bool", True, "Show WT Regular Divergences", WT),
    _p("wt_show_hidden_div", "bool", False, "Show WT Hidden Divergences", WT),
    _p("show_hidden_div_nl", "bool", True, "Not apply OB/OS Limits on Hidden Divergences", WT),
    _int("wt_div_ob_level", 45, "WT Bearish Divergence min", WT),
    _int("wt_div_os_level", -65, "WT Bullish Divergence min", WT),
    _p("wt_div_add_show", "bool", True, "Show 2nd WT Regular Divergences", WT),
    _int("wt_div_ob_level_add", 15, "WT 2nd Bearish Divergence", WT),
    _int("wt_div_os_level_add", -40, "WT 2nd Bullish Divergence 15 min", WT),
    # RSI + MFI
    _p("rsi_mfi_show", "bool", True, "Show MFI", MFI),
    _int("rsi_mfi_period", 60, "MFI Period", MFI, 1, 1000),
    _p("rsi_mfi_multiplier", "float", 150.0, "MFI Area multiplier", MFI, min=-10000, max=10000),
    _p("rsi_mfi_pos_y", "float", 2.5, "MFI Area Y Pos", MFI, min=-1000, max=1000),
    # RSI
    _p("rsi_show", "bool", True, "Show RSI", RSI),
    _p("rsi_source", "source", "close", "RSI Source", RSI),
    _int("rsi_len", 14, "RSI Length", RSI, 1, 500),
    _int("rsi_oversold", 30, "RSI Oversold", RSI, 0, 100),
    _int("rsi_overbought", 60, "RSI Overbought", RSI, 0, 100),
    _p("rsi_show_div", "bool", False, "Show RSI Regular Divergences", RSI),
    _p("rsi_show_hidden_div", "bool", False, "Show RSI Hidden Divergences", RSI),
    _int("rsi_div_ob_level", 60, "RSI Bearish Divergence min", RSI),
    _int("rsi_div_os_level", 30, "RSI Bullish Divergence min", RSI),
    # Stochastic RSI
    _p("stoch_show", "bool", True, "Show Stochastic RSI", STOCH),
    _p("stoch_use_log", "bool", True, "Use Log?", STOCH),
    _p("stoch_avg", "bool", False, "Use Average of both K & D", STOCH),
    _p("stoch_source", "source", "close", "Stochastic RSI Source", STOCH),
    _int("stoch_len", 14, "Stochastic RSI Length", STOCH, 1, 500),
    _int("stoch_rsi_len", 14, "RSI Length", STOCH, 1, 500),
    _int("stoch_k_smooth", 3, "Stochastic RSI K Smooth", STOCH, 1, 500),
    _int("stoch_d_smooth", 3, "Stochastic RSI D Smooth", STOCH, 1, 500),
    _p("stoch_show_div", "bool", False, "Show Stoch Regular Divergences", STOCH),
    _p("stoch_show_hidden_div", "bool", False, "Show Stoch Hidden Divergences", STOCH),
    # Schaff Trend Cycle
    _p("tc_line", "bool", False, "Show Schaff TC line", SCHAFF),
    _p("tc_source", "source", "close", "Schaff TC Source", SCHAFF),
    _int("tc_length", 10, "Schaff TC", SCHAFF, 1, 500),
    _int("tc_fast_length", 23, "Schaff TC Fast Lenght", SCHAFF, 1, 500),
    _int("tc_slow_length", 50, "Schaff TC Slow Length", SCHAFF, 1, 500),
    _p("tc_factor", "float", 0.5, "Schaff TC Factor", SCHAFF, min=0, max=1),
    # Sommi flag
    _p("sommi_flag_show", "bool", False, "Show Sommi flag", SOMMI),
    _p("sommi_show_vwap", "bool", False, "Show Sommi F. Wave", SOMMI),
    _p("sommi_vwap_tf", "timeframe", "12h", "Sommi F. Wave timeframe", SOMMI),
    _int("sommi_vwap_bear_level", 0, "F. Wave Bear Level (less than)", SOMMI),
    _int("sommi_vwap_bull_level", 0, "F. Wave Bull Level (more than)", SOMMI),
    _int("sommi_flag_wt_bear_level", 0, "WT Bear Level (more than)", SOMMI),
    _int("sommi_flag_wt_bull_level", 0, "WT Bull Level (less than)", SOMMI),
    _int("sommi_rsimfi_bear_level", 0, "Money flow Bear Level (less than)", SOMMI),
    _int("sommi_rsimfi_bull_level", 0, "Money flow Bull Level (more than)", SOMMI),
    # Sommi diamond
    _p("sommi_diamond_show", "bool", False, "Show Sommi diamond", SOMMI),
    _p("sommi_htc_res", "timeframe", "1h", "HTF Candle Res. 1", SOMMI),
    _p("sommi_htc_res2", "timeframe", "4h", "HTF Candle Res. 2", SOMMI),
    _int("sommi_diamond_wt_bear_level", 0, "WT Bear Level (More than)", SOMMI),
    _int("sommi_diamond_wt_bull_level", 0, "WT Bull Level (Less than)", SOMMI),
    # MACD colors / mode (no effect, see the module docstring)
    _p("macd_wt_colors_show", "bool", False, "Show MACD Colors", MACD),
    _p("macd_wt_colors_tf", "timeframe", "4h", "MACD Colors MACD TF", MACD),
    _p("dark_mode", "bool", False, "Dark mode", MODE),
    # Colors (Color Settings)
    _p("rsi_ob_color", "color", "#e13e3e", "RSI OverBought", COLORS),
    _p("rsi_os_color", "color", "#3ee145", "RSI OverSold", COLORS),
    _p("rsi_na_color", "color", "#c33ee1", "RSI InBetween", COLORS),
    _p("mfi_above_color", "color", "#3ee145", "MFI Color > 0", COLORS),
    _p("mfi_below_color", "color", "#ff3d2e", "MFI Color < 0", COLORS),
    _p("wt_bear_div_color", "color", "#e60000", "WT Bear Div", COLORS),
    _p("wt_bull_div_color", "color", "#00e676", "WT Bull Div", COLORS),
    _p("wt_buy_dot_color", "color", "#00e676", "WT Buy Dot", COLORS),
    _p("wt_sell_dot_color", "color", "#ff5252", "WT Sell Dot", COLORS),
    _p("wt1_color", "color", "#4994ec", "WT1 Fill", COLORS),
    _p("wt2_color", "color", "#1f1559", "WT2 Fill", COLORS),
    _p("vwap_color", "color", "#ffffff80", "VWAP", COLORS),
    _p("stoch_k_color", "color", "#21baf34d", "Stoch K", COLORS),
    _p("stoch_d_color", "color", "#673ab71a", "Stoch D", COLORS),
]

GREEN, RED, ORANGE = "#3fff00", "#ff0000", "#e2a400"
PINK, BLUE_LIGHT, YELLOW, WHITE = "#ff00f0", "#31c0ff", "#ffe500", "#ffffff"


# ------------------------------------------------------------------ building blocks (Pine functions)

def _sub(a, b):
    return [None if x is None or y is None else x - y for x, y in zip(a, b)]


def _lt(a, b):
    return a is not None and b is not None and a < b


def _gt(a, b):
    return a is not None and b is not None and a > b


def wavetrend(src, channel_len, average_len, ma_len):
    """f_wavetrend: [wt1, wt2] (LazyBear's WaveTrend)."""
    esa = ema(src, channel_len)
    de = ema([None if d is None else abs(d) for d in _sub(src, esa)], channel_len)
    ci = [None if None in (s, e, dv) or dv == 0 else (s - e) / (0.015 * dv) for s, e, dv in zip(src, esa, de)]
    wt1 = ema(ci, average_len)
    return wt1, sma(wt1, ma_len)


def rsi_mfi(d, period, multiplier, pos_y):
    """f_rsimfi: sma((close - open) / (high - low) * multiplier, period) - pos_y."""
    raw = [None if h == l else (c - o) / (h - l) * multiplier for o, h, l, c in zip(d.open, d.high, d.low, d.close)]
    return [None if v is None else v - pos_y for v in sma(raw, period)]


def find_divs(src, high, low, top_limit, bot_limit, use_limits):
    """f_findDivs: fractals of `src` and regular / hidden divergences against the price."""
    n = len(src)
    frac_top, frac_bot = [None] * n, [None] * n
    for i in range(4, n):
        w = [src[i - k] for k in range(5)]                  # w[k] = src[k]
        if None in w:
            continue
        if w[4] < w[2] and w[3] < w[2] and w[2] > w[1] and w[2] > w[0]:
            if not use_limits or w[2] >= top_limit:
                frac_top[i] = w[2]
        elif w[4] > w[2] and w[3] > w[2] and w[2] < w[1] and w[2] < w[0]:
            if not use_limits or w[2] <= bot_limit:
                frac_bot[i] = w[2]
    src2, high2, low2 = ago(src, 2), ago(high, 2), ago(low, 2)
    high_prev = ago(valuewhen(frac_top, src2), 2)
    high_price = ago(valuewhen(frac_top, high2), 2)
    low_prev = ago(valuewhen(frac_bot, src2), 2)
    low_price = ago(valuewhen(frac_bot, low2), 2)
    top = [truthy(v) for v in frac_top]
    bot = [truthy(v) for v in frac_bot]
    return {
        "top": top, "bot": bot, "low_prev": low_prev,
        "bear": [t and _gt(h, hp) and _lt(s, sp) for t, h, hp, s, sp in zip(top, high2, high_price, src2, high_prev)],
        "bull": [b and _lt(lo, lp) and _gt(s, sp) for b, lo, lp, s, sp in zip(bot, low2, low_price, src2, low_prev)],
        "bear_hidden": [t and _lt(h, hp) and _gt(s, sp) for t, h, hp, s, sp in zip(top, high2, high_price, src2, high_prev)],
        "bull_hidden": [b and _gt(lo, lp) and _lt(s, sp) for b, lo, lp, s, sp in zip(bot, low2, low_price, src2, low_prev)],
    }


def schaff(src, length, fast_length, slow_length, factor):
    """f_tc: Schaff Trend Cycle with Pine's nz() / na() recursion."""
    macd = _sub(ema(src, fast_length), ema(src, slow_length))
    alpha, high_ = lowest(macd, length), highest(macd, length)
    gamma, prev = [], None
    for m, a, h in zip(macd, alpha, high_):
        beta = None if a is None or h is None else h - a
        prev = (m - a) / beta * 100 if beta is not None and beta > 0 else (prev or 0.0)
        gamma.append(prev)
    delta, prev = [], None
    for g in gamma:
        prev = g if prev is None else prev + factor * (g - prev)
        delta.append(prev)
    eps, top = lowest(delta, length), highest(delta, length)
    eta, prev = [], None
    for dl, e, t in zip(delta, eps, top):
        zeta = None if e is None or t is None else t - e
        prev = (dl - e) / zeta * 100 if zeta is not None and zeta > 0 else (prev or 0.0)
        eta.append(prev)
    out, prev = [], None
    for e in eta:
        prev = e if prev is None else prev + factor * (e - prev)
        out.append(prev)
    return out


def stoch_rsi(src, stoch_len, rsi_len, smooth_k, smooth_d, use_log, use_avg):
    """f_stochrsi: [k, d]."""
    if use_log:
        src = [math.log(v) if v is not None and v > 0 else None for v in src]
    rsi = rsi_series(src, rsi_len)
    kk = sma(stoch(rsi, rsi, rsi, stoch_len), smooth_k)
    d1 = sma(kk, smooth_d)
    k = [None if a is None or b is None else (a + b) / 2 for a, b in zip(kk, d1)] if use_avg else kk
    return k, d1


def heikin_ashi_up(data):
    """Heikin-Ashi candle body direction (close > open) of every candle."""
    out, ha_open, ha_close = [], None, None
    for o, h, l, c in zip(data.open, data.high, data.low, data.close):
        ha_open = (o + c) / 2 if ha_open is None else (ha_open + ha_close) / 2
        ha_close = (o + h + l + c) / 4
        out.append(1.0 if ha_close > ha_open else 0.0)
    return out


# ------------------------------------------------------------------ the indicator

def compute(d, p):
    n = len(d.time)
    none = [None] * n
    flag = lambda values: [1.0 if v else 0.0 for v in values]   # boolean series for alerts

    rsi = rsi_series(d.source(p["rsi_source"]), p["rsi_len"])
    rsimfi = rsi_mfi(d, p["rsi_mfi_period"], p["rsi_mfi_multiplier"], p["rsi_mfi_pos_y"])
    wt1, wt2 = wavetrend(d.source(p["wt_ma_source"]), p["wt_channel_len"], p["wt_average_len"], p["wt_ma_len"])
    wt_vwap = _sub(wt1, wt2)
    wt_cross = cross(wt1, wt2)
    wt_up = [w1 is not None and w2 is not None and w2 - w1 <= 0 for w1, w2 in zip(wt1, wt2)]
    wt_down = [w1 is not None and w2 is not None and w2 - w1 >= 0 for w1, w2 in zip(wt1, wt2)]
    wt_oversold = [w is not None and w <= p["os_level"] for w in wt2]
    wt_overbought = [w is not None and w >= p["ob_level"] for w in wt2]
    stoch_k, stoch_d = stoch_rsi(d.source(p["stoch_source"]), p["stoch_len"], p["stoch_rsi_len"],
                                 p["stoch_k_smooth"], p["stoch_d_smooth"], p["stoch_use_log"], p["stoch_avg"])
    tc = schaff(d.source(p["tc_source"]), p["tc_length"], p["tc_fast_length"], p["tc_slow_length"], p["tc_factor"])

    # Other timeframes are read only when something uses them: the drawn flag / wave / diamond
    # (when switched on) or the Sommi alert conditions - otherwise e.g. a 1D chart would download
    # years of 1h candles for a hidden diamond.
    alerts_sommi = d.wants("sommi_bullish", "sommi_bearish")
    need_flag = alerts_sommi or (p["sommi_flag_show"] and d.wants("sommi_bear_flag", "sommi_bull_flag")) \
        or (p["sommi_show_vwap"] and d.wants("sommi_vwap"))
    need_diamond = alerts_sommi or (p["sommi_diamond_show"] and d.wants("sommi_bear_diamond", "sommi_bull_diamond"))

    # Sommi flag: WaveTrend "VWAP" of a higher timeframe
    htf = d.security(p["sommi_vwap_tf"]) if need_flag else None
    if htf is not None and htf.data.time:
        h1, h2 = wavetrend(htf.data.source(p["wt_ma_source"]), p["wt_channel_len"], p["wt_average_len"], p["wt_ma_len"])
        hvwap = htf.map(_sub(h1, h2))
    else:
        hvwap = none
    sommi_bear = [_lt(m, p["sommi_rsimfi_bear_level"]) and _gt(w, p["sommi_flag_wt_bear_level"]) and c and dn
                  and _lt(h, p["sommi_vwap_bear_level"])
                  for m, w, c, dn, h in zip(rsimfi, wt2, wt_cross, wt_down, hvwap)]
    sommi_bull = [_gt(m, p["sommi_rsimfi_bull_level"]) and _lt(w, p["sommi_flag_wt_bull_level"]) and c and up
                  and _gt(h, p["sommi_vwap_bull_level"])
                  for m, w, c, up, h in zip(rsimfi, wt2, wt_cross, wt_up, hvwap)]

    # Sommi diamond: Heikin-Ashi candle direction on two higher timeframes
    def ha_dir(tf):
        sec = d.security(tf) if need_diamond else None
        if sec is None or not sec.data.time:
            return [False] * n
        return [bool(v) for v in sec.map(heikin_ashi_up(sec.data))]
    dir1, dir2 = ha_dir(p["sommi_htc_res"]), ha_dir(p["sommi_htc_res2"])
    diamond_bear = [w is not None and w >= p["sommi_diamond_wt_bear_level"] and c and dn and not a and not b
                    for w, c, dn, a, b in zip(wt2, wt_cross, wt_down, dir1, dir2)]
    diamond_bull = [w is not None and w <= p["sommi_diamond_wt_bull_level"] and c and up and a and b
                    for w, c, up, a, b in zip(wt2, wt_cross, wt_up, dir1, dir2)]

    # Divergences
    wt_div = find_divs(wt2, d.high, d.low, p["wt_div_ob_level"], p["wt_div_os_level"], True)
    wt_div_add = find_divs(wt2, d.high, d.low, p["wt_div_ob_level_add"], p["wt_div_os_level_add"], True)
    wt_div_nl = find_divs(wt2, d.high, d.low, 0, 0, False)
    wt_bear_hidden = wt_div_nl["bear_hidden"] if p["show_hidden_div_nl"] else wt_div["bear_hidden"]
    wt_bull_hidden = wt_div_nl["bull_hidden"] if p["show_hidden_div_nl"] else wt_div["bull_hidden"]
    show_div, show_hidden, add_show = p["wt_show_div"], p["wt_show_hidden_div"], p["wt_div_add_show"]
    wt_bear_colored = [(show_div and a) or (show_hidden and b) for a, b in zip(wt_div["bear"], wt_bear_hidden)]
    wt_bull_colored = [(show_div and a) or (show_hidden and b) for a, b in zip(wt_div["bull"], wt_bull_hidden)]
    wt_bear_colored_add = [(show_div and add_show and a) or (show_hidden and add_show and b)
                           for a, b in zip(wt_div_add["bear"], wt_div_add["bear_hidden"])]
    wt_bull_colored_add = [(show_div and add_show and a) or (show_hidden and add_show and b)
                           for a, b in zip(wt_div_add["bull"], wt_div_add["bull_hidden"])]

    rsi_div = find_divs(rsi, d.high, d.low, p["rsi_div_ob_level"], p["rsi_div_os_level"], True)
    rsi_div_nl = find_divs(rsi, d.high, d.low, 0, 0, False)
    rsi_bear_hidden = rsi_div_nl["bear_hidden"] if p["show_hidden_div_nl"] else rsi_div["bear_hidden"]
    rsi_bull_hidden = rsi_div_nl["bull_hidden"] if p["show_hidden_div_nl"] else rsi_div["bull_hidden"]
    rsi_bear_colored = [(p["rsi_show_div"] and a) or (p["rsi_show_hidden_div"] and b)
                        for a, b in zip(rsi_div["bear"], rsi_bear_hidden)]
    rsi_bull_colored = [(p["rsi_show_div"] and a) or (p["rsi_show_hidden_div"] and b)
                        for a, b in zip(rsi_div["bull"], rsi_bull_hidden)]

    stoch_div = find_divs(stoch_k, d.high, d.low, 0, 0, False)
    stoch_bear_colored = [(p["stoch_show_div"] and a) or (p["stoch_show_hidden_div"] and b)
                          for a, b in zip(stoch_div["bear"], stoch_div["bear_hidden"])]
    stoch_bull_colored = [(p["stoch_show_div"] and a) or (p["stoch_show_hidden_div"] and b)
                          for a, b in zip(stoch_div["bull"], stoch_div["bull_hidden"])]

    # Signals
    buy = [c and u and o for c, u, o in zip(wt_cross, wt_up, wt_oversold)]
    sell = [c and dn and o for c, dn, o in zip(wt_cross, wt_down, wt_overbought)]
    buy_div = [(show_div and a) or (show_div and b) or (p["stoch_show_div"] and c) or (p["rsi_show_div"] and e)
               for a, b, c, e in zip(wt_div["bull"], wt_div_add["bull"], stoch_div["bull"], rsi_div["bull"])]
    sell_div = [(show_div and a) or (show_div and b) or (p["stoch_show_div"] and c) or (p["rsi_show_div"] and e)
                for a, b, c, e in zip(wt_div["bear"], wt_div_add["bear"], stoch_div["bear"], rsi_div["bear"])]
    buy_div_color = [0 if a else 1 if b else 0 if p["rsi_show_div"] else None
                     for a, b in zip(wt_div["bull"], wt_div_add["bull"])]
    sell_div_color = [0 if a else 1 if b else 0 if c else None
                      for a, b, c in zip(wt_div["bear"], wt_div_add["bear"], rsi_div["bear"])]
    last_rsi = ago(valuewhen(wt_div["bot"], ago(rsi, 2)), 2)
    gold = [((show_div and a) or (p["rsi_show_div"] and b)) and lp is not None and lp <= p["os_level3"]
            and _gt(w, p["os_level3"]) and lp - w <= -5 and _lt(lr, 30)
            for a, b, lp, w, lr in zip(wt_div["bull"], rsi_div["bull"], wt_div["low_prev"], wt2, last_rsi)]

    def show(values, on):
        return list(values) if on else none

    def where(cond, value):
        return [value if c else None for c in cond]

    def div_points(fractal, series, colored):
        # plot(fractal ? series[2] : na, color = colored ? color : na, offset = -2)
        return offset_left([s if f and c else None for f, s, c in zip(fractal, ago(series, 2), colored)], 2)

    mfi_on = p["rsi_mfi_show"]
    out = {
        "zero": [0.0] * n,
        "mfi_bar_top": show([-95.0] * n, mfi_on),
        "mfi_bar_bottom": show([-99.0] * n, mfi_on),
        "mfi_bar:color": [0 if _gt(m, 0) else 1 for m in rsimfi] if mfi_on else none,
        "wt1": show(wt1, p["wt_show"]),
        "wt2": show(wt2, p["wt_show"]),
        "vwap": show(wt_vwap, p["vwap_show"]),
        "rsi_mfi": show(rsimfi, mfi_on),
        "wt_bear_div": div_points(wt_div["top"], wt2, wt_bear_colored),
        "wt_bull_div": div_points(wt_div["bot"], wt2, wt_bull_colored),
        "wt_bear_div_2": div_points(wt_div_add["top"], wt2, wt_bear_colored_add),
        "wt_bull_div_2": div_points(wt_div_add["bot"], wt2, wt_bull_colored_add),
        "rsi": show(rsi, p["rsi_show"]),
        "rsi:color": [None if v is None else 1 if v <= p["rsi_oversold"] else 0 if v >= p["rsi_overbought"] else 2
                      for v in rsi],
        "rsi_bear_div": div_points(rsi_div["top"], rsi, rsi_bear_colored),
        "rsi_bull_div": div_points(rsi_div["bot"], rsi, rsi_bull_colored),
        "stoch_k": show(stoch_k, p["stoch_show"]),
        "stoch_d": show(stoch_d, p["stoch_show"]),
        "kd_fill:color": [None if None in (k, dd) else 0 if k >= dd else 1 for k, dd in zip(stoch_k, stoch_d)],
        "stoch_bear_div": div_points(stoch_div["top"], stoch_k, stoch_bear_colored),
        "stoch_bull_div": div_points(stoch_div["bot"], stoch_k, stoch_bull_colored),
        "schaff_1": show(tc, p["tc_line"]),
        "schaff_2": show(tc, p["tc_line"]),
        "ob_level2_line": [float(p["ob_level2"])] * n,
        "ob_level3_line": [float(p["ob_level3"])] * n,
        "os_level2_line": [float(p["os_level2"])] * n,
        "sommi_bear_flag": where(sommi_bear, 108.0) if p["sommi_flag_show"] else none,
        "sommi_bull_flag": where(sommi_bull, -108.0) if p["sommi_flag_show"] else none,
        "sommi_vwap": ema(hvwap, 3) if p["sommi_show_vwap"] else none,
        "sommi_bear_diamond": where(diamond_bear, 108.0) if p["sommi_diamond_show"] else none,
        "sommi_bull_diamond": where(diamond_bull, -108.0) if p["sommi_diamond_show"] else none,
        "cross_dot": [w if c else None for w, c in zip(wt2, wt_cross)],
        "cross_dot:color": [None if None in (a, b) else 1 if b - a > 0 else 0 for a, b in zip(wt1, wt2)],
        "buy_dot": where(buy, -107.0) if p["wt_buy_show"] else none,
        "sell_dot": where(sell, 105.0) if p["wt_sell_show"] else none,
        "buy_div_dot": offset_left(where(buy_div, -106.0), 2) if p["wt_div_show"] else none,
        "buy_div_dot:color": offset_left(buy_div_color, 2),
        "sell_div_dot": offset_left(where(sell_div, 106.0), 2) if p["wt_div_show"] else none,
        "sell_div_dot:color": offset_left(sell_div_color, 2),
        "gold_dot": offset_left(where(gold, -106.0), 2) if p["wt_gold_show"] else none,
        # alertcondition(...) of the original
        "buy": flag(buy),
        "buy_div": flag(buy_div),
        "gold_buy": flag(gold),
        "sommi_bullish": flag(a or b for a, b in zip(sommi_bull, diamond_bull)),
        "buy_small": flag(c and u for c, u in zip(wt_cross, wt_up)),
        "sommi_bearish": flag(a or b for a, b in zip(sommi_bear, diamond_bear)),
        "sell": flag(sell),
        "sell_div": flag(sell_div),
        "sell_small": flag(c and dn for c, dn in zip(wt_cross, wt_down)),
    }
    return out


def _points(name, color, label, radius=2.0, **kw):
    return Output(name, "points", color=color, radius=radius, label=label, alert=False, **kw)


OUTPUTS = [
    Output("zero", color=WHITE, opacity=0.5, alert=False),
    Output("mfi_bar_top", "none", alert=False),
    Output("mfi_bar_bottom", "none", alert=False),
    Output("mfi_bar", "band", between=("mfi_bar_top", "mfi_bar_bottom"), palette=("@mfi_above_color", "@mfi_below_color"),
           opacity=0.25, label="MFI Bar Colors", alert=False),
    Output("wt1", "area", color="@wt1_color", opacity=0.7, label="WT Wave 1"),
    Output("wt2", "area", color="@wt2_color", opacity=0.75, label="WT Wave 2"),
    Output("vwap", "area", color="@vwap_color", width=2, label="VWAP"),
    Output("rsi_mfi", "area", color="@mfi_above_color", color_below="@mfi_below_color", opacity=0.5, label="rsiMFI"),
    _points("wt_bear_div", "@wt_bear_div_color", "WT Bearish Divergence"),
    _points("wt_bull_div", "@wt_bull_div_color", "WT Bullish Divergence"),
    _points("wt_bear_div_2", "@wt_bear_div_color", "WT 2nd Bearish Divergence"),
    _points("wt_bull_div_2", "@wt_bull_div_color", "WT 2nd Bullish Divergence"),
    Output("rsi", palette=("@rsi_ob_color", "@rsi_os_color", "@rsi_na_color"), opacity=0.75, width=2, label="RSI"),
    _points("rsi_bear_div", "#e60000", "RSI Bearish Divergence", 1.5),
    _points("rsi_bull_div", "#38ff42", "RSI Bullish Divergence", 1.5),
    Output("kd_fill", "band", between=("stoch_k", "stoch_d"), palette=("#21baf30d", "#673ab71a"), label="KD Fill",
           alert=False),
    Output("stoch_k", color="@stoch_k_color", width=2, label="Stoch K"),
    Output("stoch_d", color="@stoch_d_color", label="Stoch D"),
    _points("stoch_bear_div", "#e60000", "Stoch Bearish Divergence", 1.5),
    _points("stoch_bull_div", "#38ff42", "Stoch Bullish Divergence", 1.5),
    Output("schaff_1", color="#673ab7", opacity=0.75, width=2, label="Schaff Trend Cycle 1"),
    Output("schaff_2", color=WHITE, opacity=0.5, label="Schaff Trend Cycle 2", alert=False),
    Output("ob_level2_line", "stepline", color=WHITE, opacity=0.15, label="Over Bought Level 2", alert=False),
    _points("ob_level3_line", WHITE, "Over Bought Level 3", 1.0, opacity=0.05),
    Output("os_level2_line", "stepline", color=WHITE, opacity=0.15, label="Over Sold Level 2", alert=False),
    Output("sommi_bear_flag", "char", color=PINK, char="⚑", label="Sommi bearish flag", alert=False),
    Output("sommi_bull_flag", "char", color=BLUE_LIGHT, char="⚑", label="Sommi bullish flag", alert=False),
    Output("sommi_vwap", color=YELLOW, opacity=0.45, width=2, label="Sommi higher VWAP"),
    Output("sommi_bear_diamond", "char", color=PINK, char="◆", label="Sommi bearish diamond", alert=False),
    Output("sommi_bull_diamond", "char", color=BLUE_LIGHT, char="◆", label="Sommi bullish diamond", alert=False),
    _points("cross_dot", None, "Buy and sell circle", 3.0, palette=("@wt_buy_dot_color", "@wt_sell_dot_color"),
            opacity=0.85),
    _points("buy_dot", GREEN, "Buy circle", 2.0, opacity=0.5),
    _points("sell_dot", RED, "Sell circle", 2.0, opacity=0.5),
    _points("buy_div_dot", None, "Divergence buy circle", 3.0, palette=(GREEN, "#3fff0066"), opacity=0.85),
    _points("sell_div_dot", None, "Divergence sell circle", 3.0, palette=(RED, "#ff000066"), opacity=0.85),
    _points("gold_dot", ORANGE, "Gold buy gold circle", 4.0, opacity=0.85),
] + [
    Output(name, "none", label=label)
    for name, label in (
        ("buy", "Buy (Big green circle)"), ("buy_div", "Buy (Big green circle + Div)"),
        ("gold_buy", "GOLD Buy (Big GOLDEN circle)"), ("sommi_bullish", "Sommi bullish flag/diamond"),
        ("buy_small", "Buy (Small green dot)"), ("sommi_bearish", "Sommi bearish flag/diamond"),
        ("sell", "Sell (Big red circle)"), ("sell_div", "Sell (Big red circle + Div)"),
        ("sell_small", "Sell (Small red dot)"),
    )
]


def warmup(p):
    return max(
        10 * p["rsi_len"] + 5,
        10 * p["stoch_rsi_len"] + p["stoch_len"] + p["stoch_k_smooth"] + p["stoch_d_smooth"],
        p["rsi_mfi_period"] + 5,
        6 * (p["wt_channel_len"] + p["wt_average_len"]) + p["wt_ma_len"],
        6 * p["tc_slow_length"] + 4 * p["tc_length"] + 40,
    )


register(Indicator(
    id="vmc_cipher_b", name="VuManChu Cipher B + Divergences", pane="separate",
    params=PARAMS,
    outputs=OUTPUTS,
    compute=compute,
    warmup=warmup,
    summary=("wt_channel_len", "wt_average_len", "wt_ma_len"),
    description="VuManChu B Divergences (VMC Cipher_B_Divergences) - WaveTrend, MFI, RSI, Stoch RSI, divergences",
))
