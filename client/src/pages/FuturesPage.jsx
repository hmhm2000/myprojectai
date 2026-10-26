import { Fragment, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { futuresApi, portfoliosApi } from "../api/endpoints";
import { ErrorBanner, Pnl } from "../components/ui";
import { hasTranslation, t } from "../i18n";
import { fmtDateTime, fmtDuration, fmtMoney, fmtPct, fmtQty, fmtUnitPrice, toNumber } from "../lib/format";

const PAGE = 100;
const GROUPS = ["contract", "account", "month"];
const SIDE_TONE = { long: "text-profit", short: "text-loss" };
const accountName = (a) => (hasTranslation(`futures.accounts.${a}`) ? t(`futures.accounts.${a}`) : a);

/** Totals of a list of positions (the same numbers as the backend's, but for the filtered list). */
function totals(positions) {
  const sum = (key) => positions.reduce((s, p) => s + (toNumber(p[key]) ?? 0), 0);
  const closed = positions.filter((p) => p.status === "closed");
  const wins = closed.filter((p) => toNumber(p.net) > 0).length;
  return {
    count: positions.length, closed: closed.length, open: positions.length - closed.length,
    wins, losses: closed.length - wins, winRate: closed.length ? (wins / closed.length) * 100 : null,
    pnl: sum("pnl"), fees: sum("fees"), funding: sum("funding"), net: sum("net"),
    liquidations: positions.filter((p) => p.liquidated).length,
  };
}

function Tile({ label, children, detail }) {
  return (
    <div className="tile p-3">
      <div className="text-[11px] uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-100">{children}</div>
      {detail && <div className="text-xs text-zinc-500">{detail}</div>}
    </div>
  );
}

function Breakdown({ positions, onPick }) {
  const [by, setBy] = useState("contract");
  const rows = useMemo(() => {
    const groups = new Map();
    for (const p of positions) {
      const key = by === "contract" ? p.contract : by === "account" ? p.account : (p.closed_at ?? p.opened_at).slice(0, 7);
      groups.set(key, [...(groups.get(key) ?? []), p]);
    }
    const list = [...groups].map(([key, items]) => ({ key, ...totals(items) }));
    return by === "month" ? list.sort((a, b) => b.key.localeCompare(a.key)) : list.sort((a, b) => a.net - b.net);
  }, [positions, by]);

  return (
    <section className="tile p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("futures.breakdown.title")}</h2>
        <div className="flex gap-1" role="group">
          {GROUPS.map((g) => (
            <button key={g} type="button" onClick={() => setBy(g)}
              className={`rounded-lg px-2.5 py-1 text-xs ${g === by ? "bg-neon-violet/20 text-zinc-50" : "text-zinc-400 hover:bg-white/5"}`}>
              {t(`futures.breakdown.${g}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="max-h-80 overflow-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="sticky top-0 bg-ink-900 text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <tr>
              {["key", "positions", "winRate", "pnl", "fees", "funding", "net"].map((k) => (
                <th key={k} className="px-2 py-1 font-medium">{t(`futures.columns.${k}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody className="num">
            {rows.map((r) => (
              <tr key={r.key} className={`border-t border-white/[0.04] ${by !== "month" ? "cursor-pointer hover:bg-white/[0.02]" : ""}`}
                onClick={() => by !== "month" && onPick(by, r.key)}>
                <td className="px-2 py-1.5 font-semibold text-zinc-100">{by === "account" ? accountName(r.key) : r.key}</td>
                <td className="px-2 py-1.5">{r.count}</td>
                <td className="px-2 py-1.5">{r.winRate === null ? "—" : fmtPct(r.winRate, { signed: false })}</td>
                <td className="px-2 py-1.5"><Pnl value={r.pnl} /></td>
                <td className="px-2 py-1.5 text-zinc-400">{fmtMoney(r.fees)}</td>
                <td className="px-2 py-1.5"><Pnl value={r.funding} /></td>
                <td className="px-2 py-1.5"><Pnl value={r.net} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {by !== "month" && <p className="mt-2 text-xs text-zinc-500">{t("futures.breakdown.hint")}</p>}
    </section>
  );
}

function Fills({ position }) {
  return (
    <div className="bg-white/[0.02] p-3">
      <div className="label">{t("futures.fills.title", { count: position.fills.length })}</div>
      <div className="overflow-x-auto">
        <table className="num w-full text-xs">
          <thead className="text-left text-zinc-500">
            <tr>
              {["time", "action", "quantity", "price", "pnl", "fee", "funding"].map((k) => (
                <th key={k} className="px-1 py-0.5 font-normal">{t(`futures.fills.${k}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {position.fills.map((f, i) => (
              <tr key={i} className="border-t border-white/[0.04] text-zinc-300">
                <td className="whitespace-nowrap px-1 py-0.5">{fmtDateTime(f.time)}</td>
                <td className="px-1 py-0.5">
                  {t(`futures.fills.actions.${f.action}`)}
                  {f.liquidation && <span className="ml-1 text-loss">({t("futures.fills.liquidation")})</span>}
                </td>
                <td className="px-1 py-0.5">{f.action === "funding" ? "—" : fmtQty(f.quantity)}</td>
                <td className="px-1 py-0.5">{f.price === null ? "—" : fmtUnitPrice(f.price)}</td>
                <td className="px-1 py-0.5">{toNumber(f.pnl) ? <Pnl value={f.pnl} /> : "—"}</td>
                <td className="px-1 py-0.5">{toNumber(f.fee) ? fmtMoney(f.fee) : "—"}</td>
                <td className="px-1 py-0.5">{toNumber(f.funding) ? <Pnl value={f.funding} /> : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Futures view: positions rebuilt from the imported fills, their result and summaries. */
export default function FuturesPage() {
  const [params, setParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState([]);
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({ account: "", contract: "", side: "", status: "", result: "" });
  const [open, setOpen] = useState(null);
  const [limit, setLimit] = useState(PAGE);
  const [error, setError] = useState(null);
  const portfolioId = Number(params.get("portfolio")) || portfolios[0]?.id;

  useEffect(() => {
    portfoliosApi.list().then(setPortfolios).catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    if (!portfolioId) return;
    setData(null);
    futuresApi.overview(portfolioId).then(setData).catch((err) => setError(errorMessage(err)));
  }, [portfolioId]);

  const positions = useMemo(() => data?.positions ?? [], [data]);
  const options = useMemo(() => ({
    account: [...new Set(positions.map((p) => p.account))].sort(),
    contract: [...new Set(positions.map((p) => p.contract))].sort(),
    side: ["long", "short"],
    status: ["open", "closed"],
    result: ["win", "loss"],
  }), [positions]);
  const shown = useMemo(() => positions.filter((p) => Object.entries(filters).every(([k, v]) => {
    if (!v) return true;
    if (k === "result") return v === "win" ? toNumber(p.net) > 0 : toNumber(p.net) <= 0;
    return p[k] === v;
  })), [positions, filters]);
  const sum = totals(shown);
  const setFilter = (key, value) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setLimit(PAGE);
  };
  const label = (key, value) => (key === "contract" ? value : key === "account" ? accountName(value)
    : t(`futures.${{ side: "sides", status: "status", result: "results" }[key]}.${value}`));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <h1 className="text-lg font-semibold text-zinc-100">{t("futures.title")}</h1>
          <p className="max-w-2xl text-xs text-zinc-500">{t("futures.intro")}</p>
        </div>
        <select value={portfolioId ?? ""} className="text-sm" onChange={(e) => setParams({ portfolio: e.target.value })}>
          {portfolios.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {Object.keys(filters).map((k) => (
          <select key={k} value={filters[k]} className="text-sm" onChange={(e) => setFilter(k, e.target.value)}>
            <option value="">{t(`futures.filters.${k}`)}</option>
            {options[k].map((v) => <option key={v} value={v}>{label(k, v)}</option>)}
          </select>
        ))}
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      {data && positions.length === 0 && <div className="tile p-6 text-center text-zinc-500">{t("futures.empty")}</div>}
      {positions.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <Tile label={t("futures.summary.net")}><Pnl value={sum.net} /></Tile>
            <Tile label={t("futures.summary.pnl")}><Pnl value={sum.pnl} /></Tile>
            <Tile label={t("futures.summary.fees")}><span className="num text-zinc-300">{fmtMoney(-sum.fees)}</span></Tile>
            <Tile label={t("futures.summary.funding")}><Pnl value={sum.funding} /></Tile>
            <Tile label={t("futures.summary.positions")}
              detail={t("futures.summary.positionsDetail", { closed: sum.closed, open: sum.open })}>{sum.count}</Tile>
            <Tile label={t("futures.summary.winRate")}
              detail={t("futures.summary.winRateDetail", { wins: sum.wins, losses: sum.losses })}>
              {sum.winRate === null ? "—" : fmtPct(sum.winRate, { signed: false })}
            </Tile>
            <Tile label={t("futures.summary.liquidations")}>
              <span className={sum.liquidations ? "text-loss" : ""}>{sum.liquidations}</span>
            </Tile>
          </div>

          <Breakdown positions={shown} onPick={setFilter} />

          <section className="tile overflow-x-auto">
            <table className="w-full min-w-[1000px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
                <tr>
                  {["date", "contract", "side", "account", "quantity", "entry", "exit", "duration", "pnl", "fees", "funding", "net"].map((k) => (
                    <th key={k} className="px-3 py-2 font-medium">{t(`futures.columns.${k}`)}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="whitespace-nowrap">
                {shown.length === 0 && (
                  <tr><td colSpan={12} className="px-3 py-6 text-center text-zinc-500">{t("futures.noMatch")}</td></tr>
                )}
                {shown.slice(0, limit).map((p) => (
                  <Fragment key={p.id}>
                    <tr className="cursor-pointer border-t border-white/[0.04] hover:bg-white/[0.02]" onClick={() => setOpen(open === p.id ? null : p.id)}>
                      <td className="whitespace-nowrap px-3 py-2 text-zinc-400">
                        {p.status === "open" ? <span className="chip text-neon-green">{t("futures.status.open")}</span> : fmtDateTime(p.closed_at)}
                      </td>
                      <td className="px-3 py-2 font-medium text-zinc-100">
                        {p.contract}
                        {p.liquidated && <span className="ml-1.5 chip text-loss">{t("futures.liquidated")}</span>}
                      </td>
                      <td className={`px-3 py-2 ${SIDE_TONE[p.side]}`}>{t(`futures.sides.${p.side}`)}</td>
                      <td className="px-3 py-2"><span className="chip whitespace-nowrap">{accountName(p.account)}</span></td>
                      <td className="num px-3 py-2">{fmtQty(p.quantity)}</td>
                      <td className="num px-3 py-2">{p.entry_price === null ? "—" : fmtUnitPrice(p.entry_price)}</td>
                      <td className="num px-3 py-2">{p.exit_price === null ? "—" : fmtUnitPrice(p.exit_price)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-zinc-400">
                        {fmtDuration(((p.closed_at ? new Date(p.closed_at) : new Date()) - new Date(p.opened_at)) / 1000)}
                      </td>
                      <td className="px-3 py-2"><Pnl value={p.pnl} /></td>
                      <td className="num px-3 py-2 text-zinc-400">{fmtMoney(p.fees)}</td>
                      <td className="px-3 py-2"><Pnl value={p.funding} /></td>
                      <td className="px-3 py-2 font-semibold"><Pnl value={p.net} /></td>
                    </tr>
                    {open === p.id && <tr><td colSpan={12} className="p-0"><Fills position={p} /></td></tr>}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {shown.length > limit && (
              <div className="border-t border-white/[0.04] p-3 text-center">
                <button type="button" className="text-sm text-neon-blue hover:underline" onClick={() => setLimit(limit + PAGE)}>
                  {t("futures.showMore", { count: shown.length - limit })}
                </button>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
