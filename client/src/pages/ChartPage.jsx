import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import CoinPicker from "../components/CoinPicker";
import ChartCell from "../components/chart/ChartCell";
import IndicatorSidebar from "../components/chart/IndicatorSidebar";
import IntervalPicker from "../components/chart/IntervalPicker";
import MarketBar from "../components/chart/MarketBar";
import Watchlist from "../components/chart/Watchlist";
import { chartIndicatorsApi, indicatorsApi } from "../api/endpoints";
import { Pnl } from "../components/ui";
import { t } from "../i18n";
import { fmtDateTime, fmtQty, fmtUnitPrice } from "../lib/format";
import { loadSymbolTrades } from "../lib/symbolTrades";
import { EyeIcon } from "../components/icons";
import { intervalLabel, parseInterval } from "../lib/intervals";

const LEGACY_INDICATORS_KEY = "chart:indicators"; // old browser-only list, imported once to the server
const SHOW_TRADES_KEY = "chart:showTrades";
const CHART_SIDE_KEY = "chart:side";   // "left" (default) | "right" - where the chart is on wide screens
const SHOW_NAMES_KEY = "chart:showNames"; // indicator names on the charts (toolbar "Nazwy")
const LAYOUT_KEY = "chart:layout";      // { count: 1 | 2 | 4, active, slots: [{ symbol, interval }] }
const LAYOUTS = [1, 2, 4];
const NO_MARKERS = [];
const DEFAULT_SLOTS = [["BTC", "1h"], ["ETH", "1h"], ["SOL", "1h"], ["BTC", "1d"]]
  .map(([symbol, interval]) => ({ symbol, interval }));

function readLayout() {
  try {
    const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY));
    const slots = DEFAULT_SLOTS.map((d, i) => ({ ...d, ...(saved?.slots?.[i] ?? {}) }));
    const count = LAYOUTS.includes(saved?.count) ? saved.count : 1;
    return { count, slots, active: Math.min(Number(saved?.active) || 0, count - 1) };
  } catch {
    return { count: 1, slots: DEFAULT_SLOTS, active: 0 };
  }
}

/** Icon of a layout: 1, 2 side by side, 2 x 2. */
function LayoutIcon({ count }) {
  const cells = { 1: [[0, 0, 14, 10]], 2: [[0, 0, 6.5, 10], [7.5, 0, 6.5, 10]],
    4: [[0, 0, 6.5, 4.5], [7.5, 0, 6.5, 4.5], [0, 5.5, 6.5, 4.5], [7.5, 5.5, 6.5, 4.5]] }[count];
  return (
    <svg width="16" height="12" viewBox="0 0 14 10" aria-hidden="true">
      {cells.map(([x, y, w, h]) => <rect key={`${x}-${y}`} x={x} y={y} width={w} height={h} rx="1" fill="currentColor" />)}
    </svg>
  );
}

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
  const [layout, setLayout] = useState(readLayout);
  const { count, slots, active } = layout;
  const { symbol, interval } = slots[active];
  const split = count > 1;

  // a link like /chart?symbol=ETH&interval=4h opens in the active window
  const urlApplied = useRef(false);
  useEffect(() => {
    if (urlApplied.current) return;
    urlApplied.current = true;
    const s = params.get("symbol")?.toUpperCase();
    const i = parseInterval(params.get("interval"));
    if (s || i) {
      setLayout((l) => ({ ...l, slots: l.slots.map((slot, n) => (n === l.active ? { symbol: s || slot.symbol, interval: i || slot.interval } : slot)) }));
    }
  }, [params]);
  useEffect(() => {
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout));
    } catch {
      // not remembered - fine
    }
    setParams({ symbol, interval }, { replace: true });
  }, [layout, symbol, interval, setParams]);

  /** Change the coin / interval of the active window. */
  const update = (changes) => setLayout((l) => ({
    ...l, slots: l.slots.map((slot, n) => (n === l.active ? { ...slot, ...changes } : slot)),
  }));
  const activate = useCallback((n) => setLayout((l) => (l.active === n ? l : { ...l, active: n })), []);
  const setCount = (n) => setLayout((l) => ({ ...l, count: n, active: Math.min(l.active, n - 1) }));

  const [eventsBy, setEventsBy] = useState({});      // symbol -> trades from the journal
  const [selected, setSelected] = useState([]);
  const [definitions, setDefinitions] = useState([]);
  const [savedIndicators, setSavedIndicators] = useState([]);
  const [showTrades, setShowTrades] = useState(() => localStorage.getItem(SHOW_TRADES_KEY) !== "false");
  const [showNames, setShowNames] = useState(() => localStorage.getItem(SHOW_NAMES_KEY) === "true");
  const [chartSide, setChartSide] = useState(() => (localStorage.getItem(CHART_SIDE_KEY) === "right" ? "right" : "left"));

  const loadIndicators = useCallback(() => chartIndicatorsApi.list().then(setSavedIndicators).catch(() => {}), []);
  // the side column adds indicators to the active window
  const slotApi = useMemo(() => ({ ...chartIndicatorsApi, add: (body) => chartIndicatorsApi.add({ ...body, slot: active }) }), [active]);

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
    localStorage.setItem(SHOW_NAMES_KEY, String(showNames));
  }, [showNames]);

  useEffect(() => {
    localStorage.setItem(CHART_SIDE_KEY, chartSide);
  }, [chartSide]);

  // journal trades of every coin on screen (loaded once per coin)
  const visibleSymbols = useMemo(() => [...new Set(slots.slice(0, count).map((s) => s.symbol))], [slots, count]);
  const requested = useRef(new Set());
  useEffect(() => {
    for (const s of visibleSymbols) {
      if (requested.current.has(s)) continue;
      requested.current.add(s);
      loadSymbolTrades(s).then((list) => setEventsBy((all) => ({ ...all, [s]: list })))
        .catch(() => requested.current.delete(s));
    }
  }, [visibleSymbols]);
  useEffect(() => setSelected([]), [symbol]);

  // Stable per-window inputs: a window redraws only when ITS indicators / markers change (new arrays on
  // every render made every window rebuild all its indicator series on each click - very slow with 2-4).
  const indicatorsBySlot = useMemo(
    () => [0, 1, 2, 3].map((n) => savedIndicators.filter((i) => (i.slot ?? 0) === n)),
    [savedIndicators],
  );
  // Only trades marked "show on chart"; the marker uses the real trade time and price.
  const markersBySymbol = useMemo(() => Object.fromEntries(Object.entries(eventsBy).map(([s, list]) => [
    s, (showTrades ? list : []).filter((e) => e.showOnChart).map(({ id, side, time, price }) => ({ id, side, time, price })),
  ])), [eventsBy, showTrades]);
  const onMarkerClick = useCallback((hits) => setSelected(hits.map((m) => m.id)), []);
  // a dragged pane border: the new height is kept for that indicator (every interval, every visit)
  const onPaneResize = useCallback((id, px) => {
    setSavedIndicators((list) => list.map((i) => (i.id === id ? { ...i, pane_height: px } : i)));
    chartIndicatorsApi.update(id, { pane_height: px }).catch(() => {});
  }, []);

  const allEvents = Object.values(eventsBy).flat();
  const selectedEvents = allEvents.filter((e) => selected.includes(e.id));

  const right = chartSide === "right";
  return (
    // Wide screens: charts + side column next to each other, both exactly as high as the window, each
    // scrolling on its own - the charts stay in view. Phones: one column, charts on top (not sticky).
    <div className={`grid gap-3 lg:sticky lg:top-[69px] lg:h-[calc(100vh-81px)] ${
      right ? "lg:grid-cols-[22rem_minmax(0,1fr)]" : "lg:grid-cols-[minmax(0,1fr)_22rem]"}`}>
      {/* the chart column never scrolls: the charts (with all their panes) always fit the window */}
      <section className={`flex min-w-0 flex-col gap-2 lg:h-full lg:min-h-0 lg:overflow-hidden ${right ? "lg:order-2" : ""}`}>
        <MarketBar />
        <div className="flex flex-wrap items-center gap-3">
          <div className="w-56">
            <CoinPicker key={`${active}-${symbol}`} value={symbol} onChange={(s) => s && update({ symbol: s })} />
          </div>
          <IntervalPicker value={interval} onChange={(value) => update({ interval: value })} />
          <button type="button" aria-pressed={showNames} title={t("chart.layout.namesHint")}
            onClick={() => setShowNames((v) => !v)}
            className={`ml-auto rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
              showNames ? "bg-neon-violet/20 text-zinc-50" : "text-zinc-500 hover:bg-white/5"}`}>
            {t("chart.layout.names")}
          </button>
          <div className="flex gap-1" role="group" aria-label={t("chart.layout.windows")}>
            {LAYOUTS.map((n) => (
              <button key={n} type="button" title={t("chart.layout.count", { count: n })} aria-pressed={count === n}
                onClick={() => setCount(n)}
                className={`rounded-lg px-2 py-1.5 transition ${count === n ? "bg-neon-violet/20 text-zinc-50" : "text-zinc-500 hover:bg-white/5"}`}>
                <LayoutIcon count={n} />
              </button>
            ))}
          </div>
        </div>
        <div className={`grid min-h-0 gap-2 lg:flex-1 ${count === 1 ? "" : count === 2 ? "lg:grid-cols-2" : "lg:grid-cols-2 lg:grid-rows-2"}`}>
          {slots.slice(0, count).map((slot, n) => (
            <ChartCell
              key={n}
              slot={n}
              symbol={slot.symbol}
              interval={slot.interval}
              indicators={indicatorsBySlot[n]}
              definitions={definitions}
              markers={markersBySymbol[slot.symbol] ?? NO_MARKERS}
              active={n === active}
              split={split}
              showNames={showNames}
              onActivate={activate}
              onMarkerClick={onMarkerClick}
              onPaneResize={onPaneResize}
            />
          ))}
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
        {split && <p className="text-xs text-zinc-500">{t("chart.layout.activeHint", { symbol, interval: intervalLabel(interval) })}</p>}

        <div className="tile p-3">
          <Watchlist symbol={symbol} onSelect={(s) => update({ symbol: s })} />
        </div>

        <div className="tile p-3">
          <IndicatorSidebar definitions={definitions} items={indicatorsBySlot[active]}
            chartInterval={interval} api={slotApi} onChanged={loadIndicators} />
        </div>

        {selectedEvents.length > 0 && (
          <div className="tile space-y-3 p-4">
            {selectedEvents.map((event) => <TradeEvent key={event.id} event={event} />)}
          </div>
        )}

      </aside>
    </div>
  );
}
