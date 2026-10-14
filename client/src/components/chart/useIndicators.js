import { useCallback, useEffect, useRef } from "react";
import { indicatorsApi } from "../../api/endpoints";
import { PRICE_PANE_SHARE, createOutputSeries, drawOutputs, paneHeight, removeOutputSeries } from "./indicatorSeries";

const TAIL_STEPS = 5; // on refresh only the newest candles are recomputed
const REMEMBERED_CHARTS = 12; // (symbol, interval) pairs whose indicator values stay in memory

// Remembered values cut to the chart's candles (a new chart starts with the newest ones only - values
// further back would stretch the time axis past the candles).
function restore(known, first) {
  if (!known || known.first === null || known.last < first) return null;
  if (known.first >= first) return known;
  const values = new Map([...known.values].map(([name, byTime]) =>
    [name, new Map([...byTime].filter(([unix]) => unix >= first))]));
  return { values, first, last: known.last };
}

// Fetched values per chart (symbol|interval) -> uid -> { values, first, last }, shared by all chart windows.
// Switching back to an interval draws its indicators at once and fetches only the newest candles.
const memory = new Map();
function remembered(symbol, interval) {
  const key = `${symbol}|${interval}`;
  const layers = memory.get(key) ?? new Map();
  memory.delete(key);
  memory.set(key, layers);   // most recently used last
  while (memory.size > REMEMBERED_CHARTS) memory.delete(memory.keys().next().value);
  return layers;
}

/**
 * Draws backend-computed indicators on a CandleChart.
 * - `api` comes from CandleChart's onReady (a new chart for every symbol/interval),
 * - `active`: [{ uid, id, params, interval, axisValue }] (interval = own timeframe or null), `definitions`: GET /api/indicators,
 * - overlays are drawn on the price pane; other indicators get their own native pane below it with
 *   their preferred height; when they do not fit, they shrink together and the price pane keeps at
 *   least half of the chart (the whole chart stays in view; pane borders can be dragged),
 * - returns `onBarsChange` to pass to CandleChart: fetches only what changed (older history or the tail).
 * Fetched values are kept per indicator (uid) and chart (symbol + interval, see `memory`), so adding,
 * editing, hiding or showing one indicator does not download the others again, and coming back to an
 * interval draws at once - only the newest candles (TAIL_STEPS) and any older history are fetched.
 */
export function useIndicators(api, active, definitions, symbol, interval) {
  const layers = useRef([]); // [{ uid, def, params, series: {output: { series, markers }}, values: Map<output, Map<unix, value>> }]
  const range = useRef(null); // { first, last } of the data already fetched

  const draw = useCallback((layer) => {
    if (api) drawOutputs(api, layer);
  }, [api]);

  const fetchInto = useCallback(async (layer, start, end) => {
    if (start > end) return;
    const result = await indicatorsApi.values(layer.id, {
      symbol, interval, start, end, params: layer.params, indicatorInterval: layer.interval !== interval ? layer.interval : null,
    });
    result.time.forEach((unix, i) => {
      for (const [name, values] of Object.entries(result.outputs)) {
        if (!layer.values.has(name)) layer.values.set(name, new Map());
        layer.values.get(name).set(unix, values[i]);
      }
    });
    layer.first = Math.min(layer.first ?? start, start);
    layer.last = Math.max(layer.last ?? end, end);
    draw(layer);
  }, [symbol, interval, draw]);

  // (Re)create series when the chart or the list of active indicators changes.
  useEffect(() => {
    // the chart of the previous coin / interval is still on screen for a moment after a switch: leave it
    if (!api || !definitions.length || api.symbol !== symbol || api.interval !== interval) return undefined;
    const bars = api.getBars();
    if (!bars.length) return undefined;
    const first = bars[0].unix;
    const last = bars[bars.length - 1].unix;
    range.current = { first, last };
    const saved = remembered(symbol, interval);

    let pane = 0;
    const heights = [0];  // px of every indicator pane (index 0 = price pane, sized from what is left)
    layers.current = active
      .map(({ uid, id, params, interval: ownInterval, axisValue }) => {
        const def = definitions.find((d) => d.id === id);
        if (!def) return null;
        const paneIndex = def.pane === "overlay" ? 0 : ++pane;
        if (paneIndex) {
          if (paneIndex >= api.chart.panes().length) api.chart.addPane();   // native v5 pane below the price
          heights[paneIndex] = paneHeight(def);
        }
        const series = createOutputSeries(api.chart, def, params, paneIndex, axisValue);
        const firstSeries = Object.values(series).find((s) => s.series)?.series;
        def.levels.forEach((price) => firstSeries?.createPriceLine({ price, color: "rgba(161,161,170,0.4)", lineStyle: 2, lineWidth: 1, axisLabelVisible: false }));
        const known = restore(saved.get(uid), first);
        return { uid, id, def, params, interval: ownInterval ?? null, series, values: known?.values ?? new Map(),
          first: known?.first ?? null, last: known?.last ?? null };
      })
      .filter(Boolean);

    // Pane sizes - also after every resize of the chart.
    const layout = () => {
      const total = Math.max(api.container.clientHeight - 30, 100);   // minus the time axis
      const wanted = heights.slice(1).reduce((sum, h) => sum + h, 0);
      const price = Math.max(total - wanted, total * PRICE_PANE_SHARE);
      const scale = wanted > 0 ? Math.min(1, (total - price) / wanted) : 1;
      api.chart.panes().forEach((p, i) => p.setStretchFactor(i === 0 ? price : (heights[i] ?? 150) * scale));
    };
    layout();
    const resize = new ResizeObserver(layout);
    resize.observe(api.container);
    const tailStart = bars[Math.max(0, bars.length - TAIL_STEPS)].unix;
    layers.current.forEach((layer) => {
      if (layer.first === null) {
        fetchInto(layer, first, last).catch(() => {});
        return;
      }
      // already fetched for this chart: draw from memory, fetch only what is missing
      draw(layer);
      if (first < layer.first) fetchInto(layer, first, layer.first - 1).catch(() => {});
      fetchInto(layer, Math.min(layer.last, tailStart), last).catch(() => {});
    });

    // Take the series off once: when the list changes, or - before that - when the chart itself is
    // about to be removed (a new coin / interval). Never touch a removed chart.
    let cleaned = false;
    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      resize.disconnect();
      for (const layer of layers.current) {
        saved.set(layer.uid, { values: layer.values, first: layer.first, last: layer.last });
        if (!api.removed) removeOutputSeries(api, layer.series);
        layer.series = {};
      }
      layers.current = [];
    };
    const unregister = api.onDispose?.(cleanup);
    return () => {
      unregister?.();
      cleanup();
    };
  }, [api, active, definitions, symbol, interval, fetchInto, draw]);

  // Called by CandleChart whenever the loaded candle range changes.
  return useCallback(({ first, last }) => {
    const known = range.current;
    if (!known || !layers.current.length || api?.symbol !== symbol || api?.interval !== interval) return;
    if (first < known.first) {
      // older history was loaded -> fetch only the new (older) part
      layers.current.forEach((layer) => fetchInto(layer, first, known.first - 1).catch(() => {}));
    } else {
      // periodic refresh -> recompute only the newest candles
      const bars = api.getBars();
      const tailStart = bars[Math.max(0, bars.length - TAIL_STEPS)].unix;
      layers.current.forEach((layer) => fetchInto(layer, tailStart, last).catch(() => {}));
    }
    range.current = { first: Math.min(first, known.first), last: Math.max(last, known.last) };
  }, [api, symbol, interval, fetchInto]);
}
