import { useEffect, useMemo, useRef, useState } from "react";
import { summaryText } from "../../lib/indicatorMeta";
import { labelColor, styledDef } from "./indicatorSeries";

const POLL_MS = 400; // pane borders can be dragged and the chart resized - positions are re-read this often

/**
 * Names of the indicators drawn on the chart ("Nazwy" in the toolbar), at the top-right of their pane,
 * just left of the price axis (the candle legend is on the left). Overlays are stacked on the price pane.
 * Pane order is the same as in useIndicators: overlay -> pane 0, the others -> 1, 2, 3... in list order.
 */
export default function IndicatorNames({ chartApi, indicators, definitions }) {
  const box = useRef(null);
  const [place, setPlace] = useState(null); // { right, tops: [px per pane] }

  const labels = useMemo(() => {
    let pane = 0;
    return indicators.map((a) => {
      const def = definitions.find((d) => d.id === a.id);
      if (!def) return null;
      return { uid: a.uid, pane: def.pane === "overlay" ? 0 : ++pane, text: summaryText(def, a.params), color: labelColor(styledDef(def, a.styles), a.params) };
    }).filter(Boolean);
  }, [indicators, definitions]);

  useEffect(() => {
    if (!chartApi) return undefined;
    let last = "";
    const read = () => {
      if (chartApi.removed || !box.current) return;
      const origin = box.current.getBoundingClientRect();
      const tops = chartApi.chart.panes().map((p) => {
        const el = p.getHTMLElement();
        return el ? Math.round(el.getBoundingClientRect().top - origin.top) : null;
      });
      const next = { right: Math.round(chartApi.chart.priceScale("right").width()) + 6, tops };
      const key = JSON.stringify(next);
      if (key !== last) {
        last = key;
        setPlace(next);
      }
    };
    read();
    const timer = setInterval(read, POLL_MS);
    return () => clearInterval(timer);
  }, [chartApi]);

  const byPane = new Map();
  labels.forEach((l) => byPane.set(l.pane, [...(byPane.get(l.pane) ?? []), l]));

  return (
    <div ref={box} className="pointer-events-none absolute inset-0 z-10 overflow-hidden">
      {place && [...byPane].map(([pane, items]) => place.tops[pane] != null && (
        <div key={pane} className="absolute flex flex-col items-end gap-0.5"
          style={{ top: place.tops[pane] + 4, right: place.right }}>
          {items.map((l) => (
            <span key={l.uid} className="rounded bg-ink-950/60 px-1.5 py-px text-[11px] font-medium leading-4"
              style={{ color: l.color }}>
              {l.text}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}
