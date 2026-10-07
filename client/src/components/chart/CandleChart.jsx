import { CandlestickSeries, createChart, createSeriesMarkers, HistogramSeries } from "lightweight-charts";
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../../api/client";
import { candlesApi } from "../../api/endpoints";
import { t } from "../../i18n";

const PAGE = 500;            // candles per request
const POLL_MS = 30_000;      // refresh of the last candles (the backend caches live candles for 30 s)
const LOAD_MORE_AT = 20;     // load older history when fewer bars than this remain on the left
const STEP = { "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "1d": 86400 };
const MARKER_STYLE = {
  BUY: { position: "belowBar", shape: "arrowUp", color: "#34d399" },
  SELL: { position: "aboveBar", shape: "arrowDown", color: "#f87171" },
};

// Lightweight Charts shows times in UTC - shift them so the axis shows local time.
const toChartTime = (unix) => unix - new Date(unix * 1000).getTimezoneOffset() * 60;

function toBars(candles) {
  return candles.map((c) => ({
    time: toChartTime(c.time),
    unix: c.time,
    open: Number(c.open),
    high: Number(c.high),
    low: Number(c.low),
    close: Number(c.close),
    volume: Number(c.volume),
  }));
}

const volumeBar = (bar) => ({
  time: bar.time,
  value: bar.volume,
  color: bar.close >= bar.open ? "rgba(52, 211, 153, 0.35)" : "rgba(248, 113, 113, 0.35)",
});

/** Price precision suited to the coin (BTC vs memecoins). */
function priceFormat(price) {
  const decimals = price >= 1000 ? 2 : price >= 1 ? 4 : price >= 0.01 ? 6 : 8;
  return { type: "price", precision: decimals, minMove: 1 / 10 ** decimals };
}

/**
 * Candlestick chart (TradingView Lightweight Charts) with volume, zoom/pan, lazy loading of older
 * history and periodic refresh of the newest candles.
 * - `markers`: [{ id, side: "BUY" | "SELL", time (unix s), text? }] drawn on the candle containing `time`,
 * - `onMarkerClick(markers)`: called with all markers of the clicked candle,
 * - `focusTime` (unix s): scrolls the chart to that moment (when it is within the loaded history),
 * - `onReady(api)`: exposes the chart and series so callers can add indicators,
 * - `onBarsChange({ first, last })`: unix times of the loaded range after every load/refresh,
 * - `extraPanes`: number of indicator panes below the price (the chart grows ~150 px per pane).
 */
export default function CandleChart({ symbol, interval, markers = [], onMarkerClick, focusTime = null, onReady, onBarsChange, extraPanes = 0 }) {
  const containerRef = useRef(null);
  const [state, setState] = useState({ loading: true, error: null, source: null });
  // Latest props for the chart callbacks (the chart itself is rebuilt only for a new symbol/interval).
  const markersRef = useRef(markers);
  const clickRef = useRef(onMarkerClick);
  const readyRef = useRef(onReady);
  const barsChangeRef = useRef(onBarsChange);
  const applyMarkersRef = useRef(() => {});
  const focusRef = useRef(() => {});
  clickRef.current = onMarkerClick;
  readyRef.current = onReady;
  barsChangeRef.current = onBarsChange;

  useEffect(() => {
    markersRef.current = markers;
    applyMarkersRef.current();
  }, [markers]);

  useEffect(() => {
    if (focusTime) focusRef.current(focusTime);
  }, [focusTime]);

  useEffect(() => {
    const container = containerRef.current;
    const chart = createChart(container, {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: "#a1a1aa", attributionLogo: true },
      grid: { vertLines: { color: "rgba(255,255,255,0.04)" }, horzLines: { color: "rgba(255,255,255,0.04)" } },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: "rgba(255,255,255,0.1)" },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399", downColor: "#f87171",
      borderVisible: true, borderUpColor: "#34d399", borderDownColor: "#f87171",
      wickVisible: true, wickUpColor: "#34d399", wickDownColor: "#f87171",
    });
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceScaleId: "" });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    const seriesMarkers = createSeriesMarkers(candles, []);
    const step = STEP[interval] ?? 3600;
    // Marker time -> time of the candle that contains it (chart time).
    const snap = (unix) => toChartTime(Math.floor(unix / step) * step);

    let bars = [];
    let oldestUnix = null;
    let loadingOlder = false;
    let noMoreHistory = false;
    let disposed = false;

    const applyMarkers = () => {
      if (!bars.length) return;
      const first = bars[0].time;
      const last = bars[bars.length - 1].time;
      const list = markersRef.current
        .map((m) => ({ ...MARKER_STYLE[m.side], time: snap(m.time), text: m.text ?? m.side, id: m.id }))
        .filter((m) => m.time >= first && m.time <= last)
        .sort((a, b) => a.time - b.time);
      seriesMarkers.setMarkers(list);
    };
    applyMarkersRef.current = applyMarkers;

    focusRef.current = (unix) => {
      const time = snap(unix);
      if (!bars.length || time < bars[0].time) return;
      chart.timeScale().setVisibleRange({ from: time - 60 * step, to: time + 60 * step });
    };

    const notifyBars = () => {
      if (bars.length) barsChangeRef.current?.({ first: bars[0].unix, last: bars[bars.length - 1].unix });
    };

    const setAll = () => {
      candles.setData(bars);
      volume.setData(bars.map(volumeBar));
      applyMarkers();
      notifyBars();
    };

    const loadOlder = async () => {
      if (loadingOlder || noMoreHistory || oldestUnix === null) return;
      loadingOlder = true;
      try {
        const data = await candlesApi.get(symbol, interval, { limit: PAGE, before: oldestUnix });
        if (disposed) return;
        if (!data.candles.length) {
          noMoreHistory = true;
          return;
        }
        oldestUnix = data.candles[0].time;
        bars = [...toBars(data.candles), ...bars];
        setAll();
      } catch {
        noMoreHistory = true; // e.g. no older data on the exchange
      } finally {
        loadingOlder = false;
      }
    };

    const refreshLatest = async () => {
      if (document.visibilityState !== "visible" || !bars.length) return;
      try {
        const data = await candlesApi.get(symbol, interval, { limit: 3 });
        if (disposed) return;
        for (const bar of toBars(data.candles)) {
          if (bar.time < bars[bars.length - 1].time) continue;
          if (bar.time === bars[bars.length - 1].time) bars[bars.length - 1] = bar;
          else bars.push(bar);
          candles.update(bar);
          volume.update(volumeBar(bar));
        }
        applyMarkers();
        notifyBars();
      } catch {
        // keep the chart as is; the next poll will try again
      }
    };

    (async () => {
      setState({ loading: true, error: null, source: null });
      try {
        const data = await candlesApi.get(symbol, interval, { limit: PAGE });
        if (disposed) return;
        bars = toBars(data.candles);
        oldestUnix = data.candles[0]?.time ?? null;
        if (bars.length) candles.applyOptions({ priceFormat: priceFormat(bars[bars.length - 1].close) });
        setAll();
        chart.timeScale().fitContent();
        setState({ loading: false, error: null, source: data.source });
        readyRef.current?.({ chart, candles, toChartTime, getBars: () => bars });
      } catch (err) {
        if (!disposed) setState({ loading: false, error: errorMessage(err), source: null });
      }
    })();

    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range && range.from < LOAD_MORE_AT) loadOlder();
    });
    chart.subscribeClick((param) => {
      if (!param.time || !clickRef.current) return;
      const hits = markersRef.current.filter((m) => snap(m.time) === param.time);
      if (hits.length) clickRef.current(hits);
    });
    const poll = setInterval(refreshLatest, POLL_MS);

    return () => {
      disposed = true;
      clearInterval(poll);
      chart.remove();
    };
  }, [symbol, interval]);

  return (
    <div className="relative">
      <div ref={containerRef} className="min-h-[320px] w-full" style={{ height: `calc(60vh + ${extraPanes * 150}px)` }} />
      {state.loading && <div className="absolute inset-0 grid place-items-center text-sm text-zinc-500">{t("common.loading")}</div>}
      {state.error && <div className="absolute inset-0 grid place-items-center text-sm text-loss">{state.error}</div>}
      {state.source && <div className="mt-1 text-right text-[11px] text-zinc-600">{t("chart.source", { source: state.source })}</div>}
    </div>
  );
}
