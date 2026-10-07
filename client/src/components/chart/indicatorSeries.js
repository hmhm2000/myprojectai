import { BaselineSeries, HistogramSeries, LineSeries, LineType, createSeriesMarkers } from "lightweight-charts";
import { resolveColor } from "../../lib/indicatorMeta";
import { BackgroundSeries, BandSeries } from "./bandSeries";

// How each output plot type (see server indicators/base.py Output) is drawn with Lightweight Charts.

const FALLBACK = "#a1a1aa";
const VALUE_LABEL = new Set(["line", "stepline", "area", "histogram"]);

const colorOf = (output, params) => resolveColor(output.color, params, output.opacity) ?? FALLBACK;
const paletteOf = (output, params) => (output.palette ?? []).map((c) => resolveColor(c, params, output.opacity));

/** Series for every drawn output of an indicator: { [output]: { series, markers? } }. */
export function createOutputSeries(chart, def, params, paneIndex) {
  const result = {};
  for (const output of def.outputs) {
    const color = colorOf(output, params);
    const base = {
      color, lineWidth: output.width ?? 1, priceLineVisible: false,
      lastValueVisible: output.alert !== false && VALUE_LABEL.has(output.plot), crosshairMarkerVisible: false,
    };
    let series;
    switch (output.plot) {
      case "none":
        continue;
      case "barcolor":
        result[output.name] = { barcolor: true };   // colors the price candles (CandleChart.setBarColors)
        continue;
      case "background":
        series = chart.addCustomSeries(new BackgroundSeries(), { color, priceLineVisible: false, lastValueVisible: false }, paneIndex);
        break;
      case "histogram":
        series = chart.addSeries(HistogramSeries, { ...base, priceFormat: { type: "price", precision: 4, minMove: 0.0001 } }, paneIndex);
        break;
      case "area": {
        const below = resolveColor(output.color_below ?? output.color, params, output.opacity) ?? color;
        series = chart.addSeries(BaselineSeries, {
          ...base, baseValue: { type: "price", price: 0 },
          topLineColor: color, topFillColor1: color, topFillColor2: color,
          bottomLineColor: below, bottomFillColor1: below, bottomFillColor2: below,
        }, paneIndex);
        break;
      }
      case "points":
        series = chart.addSeries(LineSeries, {
          ...base, lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: output.radius ?? 2,
        }, paneIndex);
        break;
      case "char":
        series = chart.addSeries(LineSeries, { ...base, lineVisible: false, pointMarkersVisible: false }, paneIndex);
        break;
      case "band":
        series = chart.addCustomSeries(new BandSeries(), { color, priceLineVisible: false, lastValueVisible: false }, paneIndex);
        break;
      case "stepline":
        series = chart.addSeries(LineSeries, { ...base, lineType: LineType.WithSteps }, paneIndex);
        break;
      default:
        series = chart.addSeries(LineSeries, base, paneIndex);
    }
    result[output.name] = { series, markers: output.plot === "char" ? createSeriesMarkers(series, []) : null };
  }
  return result;
}

/** Puts the fetched values of a layer ({ def, params, series, values }) on its series. */
export function drawOutputs(api, layer) {
  const { toChartTime } = api;
  const { def, params, values } = layer;
  for (const output of def.outputs) {
    const target = layer.series[output.name];
    if (!target) continue;
    const palette = paletteOf(output, params);
    const colors = values.get(`${output.name}:color`);
    const colorAt = (unix) => {
      if (!palette.length) return undefined;
      const index = colors?.get(unix);
      return index === null || index === undefined ? null : palette[index];
    };

    if (output.plot === "barcolor") {
      const shown = values.get(output.name);
      const colors = new Map();
      for (const [unix, value] of shown ?? []) {
        const color = value === null ? null : colorAt(unix);
        if (color) colors.set(unix, color);
      }
      api.setBarColors?.(colors.size ? colors : null);
      continue;
    }

    if (output.plot === "band") {
      const [upperName, lowerName] = output.between;
      const upper = values.get(upperName);
      const lower = values.get(lowerName);
      if (!upper || !lower) continue;
      const data = [...upper.keys()].sort((a, b) => a - b).map((unix) => {
        const point = { time: toChartTime(unix) };
        const color = colorAt(unix);
        if (upper.get(unix) === null || lower.get(unix) === null || color === null) return point;
        return { ...point, upper: upper.get(unix), lower: lower.get(unix), ...(color ? { fill: color } : {}) };
      });
      target.series.setData(data);
      continue;
    }

    const series = values.get(output.name);
    if (!series) continue;
    const markers = [];
    const data = [...series.entries()].sort((a, b) => a[0] - b[0]).map(([unix, value]) => {
      const point = { time: toChartTime(unix) };
      const color = colorAt(unix);
      if (value === null || (color === null && output.plot === "points")) return point; // whitespace = Pine's na
      if (output.plot === "background") return { ...point, fill: color ?? "" };
      point.value = value;
      if (color) point.color = color;
      else if (output.plot === "histogram" && !output.color) point.color = value >= 0 ? "rgba(52,211,153,0.6)" : "rgba(248,113,113,0.6)";
      if (output.plot === "char") {
        markers.push({ time: point.time, position: "atPriceMiddle", price: value, shape: "circle", size: 0.1,
          color: color ?? colorOf(output, params), text: output.char });
      }
      return point;
    });
    target.series.setData(data);
    target.markers?.setMarkers(markers);
  }
}

export function removeOutputSeries(api, seriesMap) {
  for (const { series, markers, barcolor } of Object.values(seriesMap)) {
    try {
      if (barcolor) {
        api.setBarColors?.(null);
        continue;
      }
      markers?.detach();
      api.chart.removeSeries(series);
    } catch {
      // chart already removed
    }
  }
}
