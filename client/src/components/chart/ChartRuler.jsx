import { useEffect, useState } from "react";
import { t } from "../../i18n";
import { fmtDuration, fmtPct, fmtPrice } from "../../lib/format";

const DRAG_PX = 5;   // Shift + drag: the measurement ends where the mouse is released
const UP = { fill: "rgba(59,130,246,0.18)", line: "#3b82f6", label: "#2563eb" };
const DOWN = { fill: "rgba(239,68,68,0.18)", line: "#ef4444", label: "#dc2626" };
const compact = new Intl.NumberFormat("pl-PL", { notation: "compact", maximumFractionDigits: 2 });

/** Unix time of bar `index` - past the newest candle (free space on the right) continued with its step. */
function timeAt(bars, index) {
  if (index >= 0 && index < bars.length) return bars[index].unix;
  const last = bars.length - 1;
  const step = last > 0 ? bars[last].unix - bars[last - 1].unix : 0;
  return index < 0 ? bars[0].unix + index * step : bars[last].unix + (index - last) * step;
}

function measure(bars, from, to) {
  const diff = to.price - from.price;
  const lo = Math.max(0, Math.min(from.index, to.index));
  const hi = Math.min(bars.length - 1, Math.max(from.index, to.index));
  let volume = 0;
  for (let i = lo; i <= hi; i++) volume += bars[i].volume;
  return {
    diff,
    pct: from.price ? (diff / from.price) * 100 : null,
    bars: to.index - from.index,
    seconds: Math.abs(timeAt(bars, to.index) - timeAt(bars, from.index)),
    volume,
  };
}

/**
 * Ruler like TradingView's: Shift + click starts measuring from the point under the mouse, moving the mouse
 * shows the price change (and %), the number of candles, the time and the volume between the two points;
 * the next click (or releasing after Shift + drag) freezes it, another click or Esc removes it.
 * Works on the price pane; follows scrolling and zooming. `api` = CandleChart's chart api.
 */
export default function ChartRuler({ api }) {
  const [view, setView] = useState(null);

  useEffect(() => {
    if (!api) return undefined;
    const { chart, candles, container } = api;
    let from = null;
    let to = null;
    let phase = "idle";        // "measuring" (follows the mouse) | "done" (frozen)
    let down = null;           // where Shift + click happened (px) - to tell a drag from a click
    let swallowMouse = false;

    const point = (e) => {
      const rect = container.getBoundingClientRect();
      const height = chart.panes()[0]?.getHeight() ?? rect.height;
      const x = e.clientX - rect.left;
      const y = Math.min(Math.max(e.clientY - rect.top, 0), height);   // price pane only
      const logical = chart.timeScale().coordinateToLogical(x);
      const price = candles.coordinateToPrice(y);
      return logical === null || price === null ? null : { index: Math.round(logical), price };
    };

    const render = () => {
      if (api.removed || !from || !to) {
        setView(null);
        return;
      }
      const ts = chart.timeScale();
      const x1 = ts.logicalToCoordinate(from.index);
      const x2 = ts.logicalToCoordinate(to.index);
      const y1 = candles.priceToCoordinate(from.price);
      const y2 = candles.priceToCoordinate(to.price);
      if ([x1, x2, y1, y2].some((v) => v === null)) {
        setView(null);
        return;
      }
      setView({ x1, x2, y1, y2, ...measure(api.getBars(), from, to),
        width: container.clientWidth - chart.priceScale("right").width(), height: chart.panes()[0]?.getHeight() ?? 0 });
    };

    const clear = () => {
      from = to = null;
      phase = "idle";
      render();
    };

    const onPointerDown = (e) => {
      if (api.removed || e.button !== 0) return;
      if (phase === "measuring") {
        phase = "done";
        swallowMouse = true;
        e.stopPropagation();
        render();
        return;
      }
      if (phase === "done") clear();
      if (!e.shiftKey) return;
      const p = point(e);
      if (!p) return;
      from = p;
      to = p;
      phase = "measuring";
      down = { x: e.clientX, y: e.clientY };
      swallowMouse = true;      // the chart must not start panning
      e.stopPropagation();
      e.preventDefault();
      render();
    };
    const onMouseDown = (e) => {
      if (!swallowMouse) return;
      swallowMouse = false;
      e.stopPropagation();
      e.preventDefault();
    };
    const onPointerMove = (e) => {
      if (phase !== "measuring" || api.removed) return;
      to = point(e) ?? to;
      render();
    };
    const onPointerUp = (e) => {
      if (phase === "measuring" && down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > DRAG_PX) phase = "done";
      down = null;
    };
    const onKey = (e) => {
      if (e.key === "Escape" && phase !== "idle") clear();
    };

    container.addEventListener("pointerdown", onPointerDown, true);
    container.addEventListener("mousedown", onMouseDown, true);
    container.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("keydown", onKey);
    // redraw when the chart is scrolled / zoomed or the price scale changes
    chart.timeScale().subscribeVisibleLogicalRangeChange(render);
    chart.subscribeCrosshairMove(render);
    return () => {
      container.removeEventListener("pointerdown", onPointerDown, true);
      container.removeEventListener("mousedown", onMouseDown, true);
      container.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("keydown", onKey);
      if (!api.removed) {
        chart.timeScale().unsubscribeVisibleLogicalRangeChange(render);
        chart.unsubscribeCrosshairMove(render);
      }
      setView(null);
    };
  }, [api]);

  if (!view) return null;
  const { x1, x2, y1, y2, width, height } = view;
  const tone = view.diff >= 0 ? UP : DOWN;
  const left = Math.min(x1, x2);
  const top = Math.min(y1, y2);
  const w = Math.max(Math.abs(x2 - x1), 1);
  const h = Math.max(Math.abs(y2 - y1), 1);
  const midX = left + w / 2;
  const midY = top + h / 2;
  // label: under the box when the price falls, above it when it rises (like TradingView)
  const labelBelow = view.diff < 0;
  const sign = view.diff > 0 ? "+" : view.diff < 0 ? "−" : "";

  return (
    <div className="pointer-events-none absolute left-0 top-0 z-20 overflow-hidden" style={{ width, height }}>
      <svg className="absolute inset-0" width={width} height={height}>
        <defs>
          <marker id="ruler-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill={tone.line} />
          </marker>
        </defs>
        <rect x={left} y={top} width={w} height={h} fill={tone.fill} />
        <line x1={midX} y1={y1} x2={midX} y2={y2} stroke={tone.line} strokeWidth="1.2" markerEnd={h > 8 ? "url(#ruler-arrow)" : undefined} />
        <line x1={x1} y1={midY} x2={x2} y2={midY} stroke={tone.line} strokeWidth="1.2" markerEnd={w > 8 ? "url(#ruler-arrow)" : undefined} />
      </svg>
      <div
        className="num absolute whitespace-nowrap rounded-md px-2.5 py-1.5 text-center text-[11px] leading-4 text-white shadow-lg"
        style={{
          background: tone.label,
          left: Math.min(Math.max(midX, 90), width - 90),
          top: labelBelow ? Math.min(top + h + 8, height - 60) : Math.max(top - 8, 60),
          transform: `translate(-50%, ${labelBelow ? "0" : "-100%"})`,
        }}
      >
        <div className="font-semibold">
          {sign}{fmtPrice(Math.abs(view.diff))} ({view.pct === null ? "—" : fmtPct(view.pct)})
        </div>
        <div>{t("chart.ruler.bars", { count: view.bars })}, {fmtDuration(view.seconds)}</div>
        <div className="opacity-80">{t("chart.ruler.volume", { volume: compact.format(view.volume) })}</div>
      </div>
    </div>
  );
}
