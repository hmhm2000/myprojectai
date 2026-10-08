import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import CoinPicker from "../components/CoinPicker";
import CandleChart from "../components/chart/CandleChart";
import IndicatorSidebar from "../components/chart/IndicatorSidebar";
import IntervalPicker from "../components/chart/IntervalPicker";
import { useIndicators } from "../components/chart/useIndicators";
import { PRICE_PANE_MIN, axisValueOf, paneHeight } from "../components/chart/indicatorSeries";
import { chartIndicatorsApi, indicatorsApi } from "../api/endpoints";
import { Pnl } from "../components/ui";
import { t } from "../i18n";
import { fmtDateTime, fmtQty, fmtUnitPrice } from "../lib/format";
import { loadSymbolTrades } from "../lib/symbolTrades";
import { portfoliosApi } from "../api/endpoints";
import { EyeIcon } from "../components/icons";
import { parseInterval } from "../lib/intervals";

const LEGACY_INDICATORS_KEY = "chart:indicators"; // old browser-only list, imported once to the server
const SHOW_TRADES_KEY = "chart:showTrades";
const CHART_SIDE_KEY = "chart:side";   // "left" (default) | "right" - where the chart is on wide screens

function readLegacy() {
  try {
    return JSON.parse(localStorage.getItem(LEGACY_INDICATORS_KEY)) ?? [];
  } catch {
    return [];
  }
}

/** Journal of one BUY or SELL - shown after clicking a marker or a row in the trade list. */
function TradeEvent({ event }) {
  const buy = event.side === "BUY";
  const position = event.position;
  return (
    <div className="space-y-1.5 border-t border-white/[0.05] pt-3 first:border-0 first:pt-0">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className={`font-semibold ${buy ? "text-profit" : "text-loss"}`}>{event.side} {event.symbol}</span>
        <span className="num text-zinc-100">{fmtUnitPrice(event.price)}</span>
        <span className="num text-zinc-400">{fmtQty(event.quantity)} {event.symbol}</span>
        <span className="text-xs text-zinc-500">{fmtDateTime(event.time * 1000)} · {event.portfolio}</span>
        {buy && <Pnl value={position.total_pnl} pct={position.total_pnl_pct} className="text-xs" />}
      </div>

      {buy ? (
        <>
          <Reason label={t("chart.trades.entryReason")} text={position.entry_reason} />
          {position.tags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {position.tags.map((tag) => <span key={tag} className="chip text-neon-violet">{tag}</span>)}
            </div>
          )}
          {(position.target_price || position.stop_loss) && (
            <p className="num text-xs text-zinc-400">
              {position.target_price && <span className="mr-3">TP {fmtUnitPrice(position.target_price)}</span>}
              {position.stop_loss && <span>SL {fmtUnitPrice(position.stop_loss)}</span>}
            </p>
          )}
          <Reason label={t("chart.trades.plan")} text={position.plan} />
        </>
      ) : (
        <>
          <Reason label={t("chart.trades.exitReason")} text={event.group.exit_reason} />
          <ul className="text-xs text-zinc-400">
            {event.positions.map((p) => {
              const part = event.group.parts.find((x) => x.position_id === p.id);
              return (
                <li key={p.id}>
                  {t("chart.trades.fromPosition", {
                    quantity: fmtQty(part?.quantity),
                    date: fmtDateTime(p.bought_at),
                    price: fmtUnitPrice(p.buy_price),
                  })}
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}

function Reason({ label, text }) {
  if (!text) return null;
  return (
    <p className="whitespace-pre-line text-sm text-zinc-300">
      <span className="text-xs text-zinc-500">{label}: </span>
      {text}
    </p>
  );
}

export default function ChartPage() {
  const [params, setParams] = useSearchParams();
  const symbol = (params.get("symbol") || "BTC").toUpperCase();
  const interval = parseInterval(params.get("interval")) ?? "1h";
  const update = (changes) => setParams({ symbol, interval, ...changes }, { replace: true });

  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState([]);
  const [focusTime, setFocusTime] = useState(null);
  const [chartApi, setChartApi] = useState(null);
  const [definitions, setDefinitions] = useState([]);
  const [savedIndicators, setSavedIndicators] = useState([]);
  const [showTrades, setShowTrades] = useState(() => localStorage.getItem(SHOW_TRADES_KEY) !== "false");
  const [chartSide, setChartSide] = useState(() => (localStorage.getItem(CHART_SIDE_KEY) === "right" ? "right" : "left"));
  // Visible saved indicators in the shape useIndicators expects.
  const activeIndicators = useMemo(
    () => savedIndicators.filter((i) => i.visible).map((i) => ({
      uid: `${i.id}-${i.interval}-${JSON.stringify(i.params)}`, id: i.indicator_id, params: i.params, interval: i.interval,
      axisValue: axisValueOf(i, definitions.find((d) => d.id === i.indicator_id)),
    })),
    [savedIndicators, definitions],
  );
  // price pane + every indicator pane below it (px) - the chart is never lower than that
  const chartMinHeight = PRICE_PANE_MIN + 30 + activeIndicators
    .reduce((sum, a) => sum + paneHeight(definitions.find((d) => d.id === a.id)), 0);
  const onBarsChange = useIndicators(chartApi, activeIndicators, definitions, symbol, interval);

  const loadIndicators = useCallback(() => chartIndicatorsApi.list().then(setSavedIndicators).catch(() => {}), []);

  useEffect(() => {
    indicatorsApi.list().then(setDefinitions).catch(() => {});
  }, []);

  useEffect(() => {
    // Read and remove the old browser-only list synchronously, so it is imported only once
    // (effects can run twice in development).
    const legacy = readLegacy();
    localStorage.removeItem(LEGACY_INDICATORS_KEY);
    (async () => {
      const saved = await chartIndicatorsApi.list().catch(() => null);
      if (saved && saved.length === 0 && legacy.length) {
        for (const item of legacy) await chartIndicatorsApi.add({ indicator_id: item.id, params: item.params }).catch(() => {});
      }
      loadIndicators();
    })();
  }, [loadIndicators]);

  useEffect(() => {
    localStorage.setItem(SHOW_TRADES_KEY, String(showTrades));
  }, [showTrades]);

  useEffect(() => {
    localStorage.setItem(CHART_SIDE_KEY, chartSide);
  }, [chartSide]);

  useEffect(() => {
    let cancelled = false;
    setEvents([]);
    setSelected([]);
    loadSymbolTrades(symbol).then((list) => !cancelled && setEvents(list)).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  // Only trades marked "show on chart"; the marker uses the real trade time and price.
  const markers = useMemo(
    () => (showTrades ? events : []).filter((e) => e.showOnChart).map(({ id, side, time, price }) => ({ id, side, time, price })),
    [events, showTrades],
  );

  const toggleOnChart = async (event) => {
    const show = !event.showOnChart;
    setEvents((list) => list.map((e) => (e.id === event.id ? { ...e, showOnChart: show } : e)));
    try {
      if (event.side === "BUY") await portfoliosApi.setPositionOnChart(event.position.id, show);
      else await portfoliosApi.setSaleOnChart(event.group.group_id, show);
    } catch {
      setEvents((list) => list.map((e) => (e.id === event.id ? { ...e, showOnChart: !show } : e)));
    }
  };
  const selectedEvents = events.filter((e) => selected.includes(e.id));

  const right = chartSide === "right";
  return (
    // Wide screens: chart + side column next to each other, both exactly as high as the window, each
    // scrolling on its own - the chart stays in view. Phones: one column, chart on top (not sticky).
    <div className="grid gap-3 lg:sticky lg:top-[69px] lg:h-[calc(100vh-81px)] lg:grid-cols-[minmax(0,1fr)_22rem]">
      <section className={`flex min-w-0 flex-col gap-2 lg:h-full lg:overflow-y-auto ${right ? "lg:order-2" : ""}`}>
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-56">
            <CoinPicker key={symbol} value={symbol} onChange={(s) => s && update({ symbol: s })} />
          </div>
          <IntervalPicker value={interval} onChange={(value) => update({ interval: value })} />
        </div>
        <div className="tile min-h-0 p-2 lg:flex-1" style={{ minHeight: chartMinHeight + 40 }}>
          <CandleChart
            symbol={symbol}
            interval={interval}
            markers={markers}
            focusTime={focusTime}
            onMarkerClick={(hits) => setSelected(hits.map((m) => m.id))}
            onReady={setChartApi}
            onBarsChange={onBarsChange}
            minHeight={chartMinHeight}
          />
        </div>
      </section>

      <aside className={`min-w-0 space-y-3 lg:h-full lg:overflow-y-auto lg:pr-1 ${right ? "lg:order-1" : ""}`}>
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-400">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={showTrades} onChange={(e) => setShowTrades(e.target.checked)} />
            {t("chart.trades.showAll")}
          </label>
          <button type="button" className="hidden text-zinc-400 hover:text-zinc-200 hover:underline lg:inline"
            onClick={() => setChartSide(right ? "left" : "right")}>
            {right ? t("chart.layout.chartLeft") : t("chart.layout.chartRight")}
          </button>
        </div>

        <div className="tile p-3">
          <IndicatorSidebar definitions={definitions} items={savedIndicators} chartInterval={interval}
            api={chartIndicatorsApi} onChanged={loadIndicators} />
        </div>

        {selectedEvents.length > 0 && (
          <div className="tile space-y-3 p-4">
            {selectedEvents.map((event) => <TradeEvent key={event.id} event={event} />)}
          </div>
        )}

        <div className="tile p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
            {t("chart.trades.title", { symbol })}
          </h2>
          {events.length === 0 ? (
            <p className="mt-2 text-sm text-zinc-500">{t("chart.trades.none")}</p>
          ) : (
            <ul className="mt-2 divide-y divide-white/[0.04] text-sm">
              {[...events].reverse().map((event) => (
                <li key={event.id} className={`flex items-center gap-2 ${event.showOnChart ? "" : "opacity-50"}`}>
                  <button
                    type="button"
                    className={`btn-icon h-7 w-7 shrink-0 ${event.showOnChart ? "text-neon-green" : ""}`}
                    title={event.showOnChart ? t("chart.trades.hideOnChart") : t("chart.trades.showOnChart")}
                    aria-pressed={event.showOnChart}
                    onClick={() => toggleOnChart(event)}
                  >
                    <EyeIcon size={14} />
                  </button>
                  <button
                    type="button"
                    className={`flex min-w-0 flex-1 flex-wrap items-baseline gap-x-3 py-1.5 text-left hover:bg-white/[0.03] ${
                      selected.includes(event.id) ? "bg-white/[0.05]" : ""
                    }`}
                    onClick={() => {
                      setSelected([event.id]);
                      setFocusTime(event.time);
                    }}
                  >
                    <span className={`w-10 font-semibold ${event.side === "BUY" ? "text-profit" : "text-loss"}`}>{event.side}</span>
                    <span className="text-zinc-400">{fmtDateTime(event.time * 1000)}</span>
                    <span className="num text-zinc-200">{fmtUnitPrice(event.price)}</span>
                    <span className="num text-zinc-500">{fmtQty(event.quantity)}</span>
                    <span className="truncate text-xs text-zinc-500">
                      {event.side === "BUY" ? event.position.entry_reason : event.group.exit_reason}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-[11px] text-zinc-600">{t("chart.trades.hint")}</p>
        </div>
      </aside>
    </div>
  );
}
