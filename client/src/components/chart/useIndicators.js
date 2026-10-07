import { HistogramSeries, LineSeries } from "lightweight-charts";
import { useCallback, useEffect, useRef } from "react";
import { indicatorsApi } from "../../api/endpoints";

const TAIL_STEPS = 5; // on refresh only the newest candles are recomputed

/**
 * Draws backend-computed indicators on a CandleChart.
 * - `api` comes from CandleChart's onReady (a new chart for every symbol/interval),
 * - `active`: [{ uid, id, params }], `definitions`: list from GET /api/indicators,
 * - returns `onBarsChange` to pass to CandleChart: fetches only what changed (older history or the tail).
 */
export function useIndicators(api, active, definitions, symbol, interval) {
  const layers = useRef([]); // [{ uid, def, params, series: {output: ISeriesApi}, values: Map<output, Map<unix, value>> }]
  const range = useRef(null); // { first, last } of the data already fetched

  const draw = useCallback((layer) => {
    if (!api) return;
    for (const output of layer.def.outputs) {
      const values = layer.values.get(output.name);
      const series = layer.series[output.name];
      if (!values || !series) continue;
      const data = [...values.entries()]
        .sort((a, b) => a[0] - b[0])
        .map(([unix, value]) => {
          const point = { time: api.toChartTime(unix) };
          if (value === null) return point; // whitespace = Pine's na
          point.value = value;
          if (output.plot === "histogram") point.color = value >= 0 ? "rgba(52,211,153,0.6)" : "rgba(248,113,113,0.6)";
          return point;
        });
      series.setData(data);
    }
  }, [api]);

  const fetchInto = useCallback(async (layer, start, end) => {
    const result = await indicatorsApi.values(layer.id, { symbol, interval, start, end, params: layer.params });
    result.time.forEach((unix, i) => {
      for (const [name, values] of Object.entries(result.outputs)) {
        if (!layer.values.has(name)) layer.values.set(name, new Map());
        layer.values.get(name).set(unix, values[i]);
      }
    });
    draw(layer);
  }, [symbol, interval, draw]);

  // (Re)create series when the chart or the list of active indicators changes.
  useEffect(() => {
    if (!api || !definitions.length) return undefined;
    const bars = api.getBars();
    if (!bars.length) return undefined;
    const first = bars[0].unix;
    const last = bars[bars.length - 1].unix;
    range.current = { first, last };

    let pane = 0;
    layers.current = active
      .map(({ uid, id, params }) => {
        const def = definitions.find((d) => d.id === id);
        if (!def) return null;
        const paneIndex = def.pane === "overlay" ? 0 : ++pane;
        const series = {};
        def.outputs.forEach((output) => {
          const options = { color: output.color ?? "#a1a1aa", lineWidth: 1, priceLineVisible: false, lastValueVisible: true };
          series[output.name] = output.plot === "histogram"
            ? api.chart.addSeries(HistogramSeries, { ...options, priceFormat: { type: "price", precision: 4, minMove: 0.0001 } }, paneIndex)
            : api.chart.addSeries(LineSeries, options, paneIndex);
        });
        const firstSeries = series[def.outputs[0].name];
        def.levels.forEach((price) => firstSeries.createPriceLine({ price, color: "rgba(161,161,170,0.4)", lineStyle: 2, lineWidth: 1, axisLabelVisible: false }));
        return { uid, id, def, params, series, values: new Map() };
      })
      .filter(Boolean);

    // Price pane 3 parts, each indicator pane 1 part (CandleChart grows with the number of panes).
    api.chart.panes().forEach((p, i) => p.setStretchFactor(i === 0 ? 3 : 1));
    layers.current.forEach((layer) => fetchInto(layer, first, last).catch(() => {}));

    return () => {
      for (const layer of layers.current) {
        for (const series of Object.values(layer.series)) {
          try { api.chart.removeSeries(series); } catch { /* chart already removed */ }
        }
      }
      layers.current = [];
    };
  }, [api, active, definitions, fetchInto]);

  // Called by CandleChart whenever the loaded candle range changes.
  return useCallback(({ first, last }) => {
    const known = range.current;
    if (!known || !layers.current.length) return;
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
  }, [api, fetchInto]);
}
