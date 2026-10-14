import { memo, useMemo, useState } from "react";
import { intervalLabel } from "../../lib/intervals";
import CandleChart from "./CandleChart";
import IndicatorNames from "./IndicatorNames";
import { PRICE_PANE_MIN, axisValueOf, paneHeight } from "./indicatorSeries";
import { useIndicators } from "./useIndicators";

/**
 * One chart window of the (split) chart page: its own coin, interval and indicators.
 * Clicking anywhere in it makes it the active window (the toolbar and the side column work on it).
 */
function ChartCell({ slot, symbol, interval, indicators, definitions, markers, active, split, showNames,
  onActivate, onMarkerClick }) {
  const [chartApi, setChartApi] = useState(null);
  // visible saved indicators of this window, in the shape useIndicators expects
  const activeIndicators = useMemo(
    () => indicators.filter((i) => i.visible).map((i) => ({
      uid: `${i.id}-${i.interval}-${JSON.stringify(i.params)}`, id: i.indicator_id, params: i.params, interval: i.interval,
      axisValue: axisValueOf(i, definitions.find((d) => d.id === i.indicator_id)),
    })),
    [indicators, definitions],
  );
  // phones: price pane + every indicator pane below it (px)
  const minHeight = PRICE_PANE_MIN + 30 + activeIndicators
    .reduce((sum, a) => sum + paneHeight(definitions.find((d) => d.id === a.id)), 0);
  const onBarsChange = useIndicators(chartApi, activeIndicators, definitions, symbol, interval);

  return (
    <div
      onMouseDownCapture={() => onActivate(slot)}
      className={`tile relative flex min-h-0 min-w-0 flex-col p-2 transition ${
        split ? (active ? "ring-1 ring-neon-violet/70" : "opacity-95 hover:ring-1 hover:ring-white/10") : ""}`}
    >
      {split && (
        <div className={`mb-1 px-1 text-xs font-semibold ${active ? "text-zinc-100" : "text-zinc-500"}`}>
          {symbol} · {intervalLabel(interval)}
        </div>
      )}
      <div className="relative min-h-0 flex-1">
        <CandleChart
          symbol={symbol}
          interval={interval}
          markers={markers}
          onMarkerClick={onMarkerClick}
          onReady={setChartApi}
          onBarsChange={onBarsChange}
          minHeight={split ? Math.max(260, minHeight * 0.7) : minHeight}
        />
        {showNames && <IndicatorNames chartApi={chartApi} indicators={activeIndicators} definitions={definitions} />}
      </div>
    </div>
  );
}

// re-renders only when its own props change (another window or the side column do not touch it)
export default memo(ChartCell);
