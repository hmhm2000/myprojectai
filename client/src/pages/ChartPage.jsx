import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import CoinPicker from "../components/CoinPicker";
import CandleChart from "../components/chart/CandleChart";
import { Pnl } from "../components/ui";
import { t } from "../i18n";
import { fmtDateTime, fmtQty, fmtUnitPrice } from "../lib/format";
import { loadSymbolTrades } from "../lib/symbolTrades";

const INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

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
  const interval = INTERVALS.includes(params.get("interval")) ? params.get("interval") : "1h";
  const update = (changes) => setParams({ symbol, interval, ...changes }, { replace: true });

  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState([]);
  const [focusTime, setFocusTime] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setEvents([]);
    setSelected([]);
    loadSymbolTrades(symbol).then((list) => !cancelled && setEvents(list)).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const markers = useMemo(() => events.map(({ id, side, time }) => ({ id, side, time })), [events]);
  const selectedEvents = events.filter((e) => selected.includes(e.id));

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-56">
          <CoinPicker key={symbol} value={symbol} onChange={(s) => s && update({ symbol: s })} />
        </div>
        <div className="flex flex-wrap gap-1">
          {INTERVALS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => update({ interval: value })}
              className={`rounded-lg px-2.5 py-1.5 text-xs transition ${
                value === interval ? "bg-neon-violet/20 text-zinc-50" : "text-zinc-400 hover:bg-white/5"
              }`}
            >
              {t(`chart.intervals.${value}`)}
            </button>
          ))}
        </div>
      </div>

      <div className="tile p-2">
        <CandleChart
          symbol={symbol}
          interval={interval}
          markers={markers}
          focusTime={focusTime}
          onMarkerClick={(hits) => setSelected(hits.map((m) => m.id))}
        />
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
              <li key={event.id}>
                <button
                  type="button"
                  className={`flex w-full flex-wrap items-baseline gap-x-3 py-1.5 text-left hover:bg-white/[0.03] ${
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
    </div>
  );
}
