import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { importApi, portfoliosApi, transactionsApi } from "../api/endpoints";
import { ErrorBanner, Pnl } from "../components/ui";
import { t } from "../i18n";
import { fmtDateTime, fmtMoney, fmtQty, fmtUnitPrice } from "../lib/format";

const METHODS = ["average", "fifo", "lifo"];
const TYPE_TONE = { buy: "text-profit", sell: "text-loss", transfer_in: "text-sky-300", transfer_out: "text-amber-300",
  futures: "text-zinc-400", sell_uncovered: "text-loss" };
const dash = (v, fmt) => (v === null || v === undefined ? "—" : fmt(v));

/** Per-coin cost summary with the method switch and an own price for the unrealized result. */
function CostSummary({ portfolioId, method, onMethod, symbolFilter }) {
  const [rows, setRows] = useState([]);
  const [prices, setPrices] = useState({});      // symbol -> typed price
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    transactionsApi.summary(portfolioId, { method, symbol: symbolFilter || undefined })
      .then((list) => !cancelled && setRows(list)).catch((err) => setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [portfolioId, method, symbolFilter]);

  const applyPrice = (symbol) => {
    const price = prices[symbol];
    transactionsApi.summary(portfolioId, { method, symbol, price: price || undefined })
      .then(([row]) => row && setRows((list) => list.map((r) => (r.symbol === symbol ? row : r))))
      .catch((err) => setError(errorMessage(err)));
  };

  return (
    <section className="tile p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("transactions.summary.title")}</h2>
        <div className="flex gap-1" role="group" aria-label={t("transactions.summary.method")}>
          {METHODS.map((m) => (
            <button key={m} type="button" onClick={() => onMethod(m)}
              className={`rounded-lg px-2.5 py-1 text-xs ${m === method ? "bg-neon-violet/20 text-zinc-50" : "text-zinc-400 hover:bg-white/5"}`}>
              {t(`transactions.methods.${m}`)}
            </button>
          ))}
        </div>
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <tr>
              {["coin", "balance", "averageCost", "cost", "realized", "fees", "transferredOut", "price", "unrealized"]
                .map((k) => <th key={k} className="px-2 py-1 font-medium">{t(`transactions.summary.${k}`)}</th>)}
            </tr>
          </thead>
          <tbody className="num">
            {rows.map((r) => (
              <tr key={r.symbol} className="border-t border-white/[0.04]">
                <td className="px-2 py-1.5 font-semibold text-zinc-100">{r.symbol}</td>
                <td className="px-2 py-1.5">{fmtQty(r.balance)}</td>
                <td className="px-2 py-1.5">{dash(r.average_cost, fmtUnitPrice)}</td>
                <td className="px-2 py-1.5">{fmtMoney(r.cost)}</td>
                <td className="px-2 py-1.5"><Pnl value={r.realized} /></td>
                <td className="px-2 py-1.5 text-zinc-400">{fmtMoney(r.fees)}</td>
                <td className="px-2 py-1.5 text-zinc-400">
                  {Number(r.transferred_out) ? `${fmtQty(r.transferred_out)} (${fmtMoney(r.transferred_out_cost)})` : "—"}
                </td>
                <td className="px-2 py-1.5">
                  <form className="flex items-center gap-1" onSubmit={(e) => { e.preventDefault(); applyPrice(r.symbol); }}>
                    <input inputMode="decimal" className="w-24 py-0.5 text-xs" placeholder={dash(r.price, String)}
                      value={prices[r.symbol] ?? ""} onChange={(e) => setPrices({ ...prices, [r.symbol]: e.target.value })} />
                  </form>
                </td>
                <td className="px-2 py-1.5">{r.unrealized === null ? "—" : <Pnl value={r.unrealized} />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-zinc-500">{t("transactions.summary.hint")}</p>
      {rows.some((r) => Number(r.uncovered) > 0) && (
        <p className="mt-1 text-xs text-amber-200">
          ⚠ {rows.filter((r) => Number(r.uncovered) > 0).map((r) => `${r.symbol} ${fmtQty(r.uncovered)}`).join(", ")}
          {" "}{t("transactions.summary.uncovered")}
        </p>
      )}
    </section>
  );
}

/** Note and own fields - the same for manual and imported entries. */
function DetailsEditor({ item, onSaved }) {
  const [note, setNote] = useState(item.note ?? "");
  const [fields, setFields] = useState(Object.entries(item.custom_fields ?? {}));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await transactionsApi.update(item.kind, item.id, {
        note, custom_fields: Object.fromEntries(fields.filter(([k]) => k.trim())) });
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block">
        <span className="label">{t("transactions.details.note")}</span>
        <textarea className="w-full text-sm" rows={2} maxLength={4000} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="space-y-1">
        <span className="label">{t("transactions.details.customFields")}</span>
        {fields.map(([key, value], i) => (
          <div key={i} className="flex gap-2">
            <input className="w-40 py-1 text-xs" placeholder={t("transactions.details.fieldName")} value={key}
              onChange={(e) => setFields(fields.map((f, j) => (j === i ? [e.target.value, f[1]] : f)))} />
            <input className="flex-1 py-1 text-xs" placeholder={t("transactions.details.fieldValue")} value={value}
              onChange={(e) => setFields(fields.map((f, j) => (j === i ? [f[0], e.target.value] : f)))} />
            <button type="button" className="text-xs text-zinc-500 hover:text-loss"
              onClick={() => setFields(fields.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        <button type="button" className="text-xs text-neon-green hover:underline" onClick={() => setFields([...fields, ["", ""]])}>
          {t("transactions.details.addField")}
        </button>
      </div>
      <ErrorBanner>{error}</ErrorBanner>
      <button type="button" className="btn-primary px-3 py-1 text-xs" disabled={busy} onClick={save}>
        {busy ? t("common.actions.saving") : t("common.actions.save")}
      </button>
    </div>
  );
}

function Details({ item, onSaved }) {
  const journal = Object.entries(item.journal ?? {}).filter(([, v]) => (Array.isArray(v) ? v.length : v));
  return (
    <div className="grid gap-4 bg-white/[0.02] p-3 lg:grid-cols-2">
      <div className="space-y-3 text-xs">
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-zinc-400">
          <dt>{t("transactions.details.source")}</dt><dd className="text-zinc-200">{item.source}</dd>
          {item.external_id && <><dt>{t("transactions.details.externalId")}</dt><dd className="num text-zinc-200">{item.external_id}</dd></>}
          {item.file && <><dt>{t("transactions.details.file")}</dt><dd className="break-all text-zinc-200">{item.file}</dd></>}
          {item.imported_at && <><dt>{t("transactions.details.importedAt")}</dt><dd className="text-zinc-200">{fmtDateTime(`${item.imported_at}Z`)}</dd></>}
          {item.unallocated && <><dt>{t("transactions.details.unallocated")}</dt><dd className="num text-amber-200">{fmtQty(item.unallocated)} {item.symbol}</dd></>}
          {journal.map(([k, v]) => (
            <Fragment key={k}><dt>{t(`transactions.journal.${k}`)}</dt><dd className="whitespace-pre-line text-zinc-200">{Array.isArray(v) ? v.join(", ") : v}</dd></Fragment>
          ))}
        </dl>
        {item.kind !== "movement" && <p className="text-zinc-500">{t("transactions.details.journalHint")}</p>}
        <DetailsEditor item={item} onSaved={onSaved} />
      </div>
      <div className="space-y-3 text-xs">
        {item.raw_rows.length > 0 && (
          <div>
            <div className="label">{t("transactions.details.raw")}</div>
            <div className="overflow-x-auto">
              <table className="num w-full">
                <tbody>
                  {Object.keys(item.raw_rows[0]).map((col) => (
                    <tr key={col} className="border-t border-white/[0.04]">
                      <th className="whitespace-nowrap px-1 py-0.5 text-left font-normal text-zinc-500">{col}</th>
                      {item.raw_rows.map((row, i) => <td key={i} className="whitespace-nowrap px-1 py-0.5 text-zinc-200">{row[col]}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {item.changes.length > 0 && (
          <div>
            <div className="label">{t("transactions.details.changes")}</div>
            <ul className="space-y-1 text-zinc-300">
              {item.changes.map((c, i) => (
                <li key={i}>{t("transactions.details.change", { field: c.field, old: c.old ?? "—", new: c.new ?? "—",
                  date: fmtDateTime(`${c.changed_at}Z`), file: c.file ?? "—" })}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

/** Transaction details view: every entry with its origin, the full export data, notes and own fields. */
export default function TransactionsPage() {
  const [params, setParams] = useSearchParams();
  const [portfolios, setPortfolios] = useState([]);
  const [items, setItems] = useState([]);
  const [method, setMethod] = useState("average");
  const [open, setOpen] = useState(null);
  const [filters, setFilters] = useState({ symbol: "", source: "", type: "" });
  const [error, setError] = useState(null);
  const portfolioId = Number(params.get("portfolio")) || portfolios[0]?.id;

  useEffect(() => {
    portfoliosApi.list().then(setPortfolios).catch((err) => setError(errorMessage(err)));
    importApi.status().then((s) => {
      setMethod(s.cost_method);
      if (!params.get("portfolio") && s.portfolio_id) setParams({ portfolio: s.portfolio_id }, { replace: true });
    }).catch(() => {});
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(() => {
    if (!portfolioId) return;
    transactionsApi.list(portfolioId).then(setItems).catch((err) => setError(errorMessage(err)));
  }, [portfolioId]);
  useEffect(load, [load]);

  const changeMethod = (m) => {
    setMethod(m);
    importApi.settings({ cost_method: m }).catch(() => {});
  };

  const options = useMemo(() => ({
    symbol: [...new Set(items.map((i) => i.symbol))].sort(),
    source: [...new Set(items.map((i) => i.source))].sort(),
    type: [...new Set(items.map((i) => i.type))],
  }), [items]);
  const shown = items.filter((i) => Object.entries(filters).every(([k, v]) => !v || i[k] === v));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="mr-auto text-lg font-semibold text-zinc-100">{t("transactions.title")}</h1>
        <select value={portfolioId ?? ""} className="text-sm" onChange={(e) => setParams({ portfolio: e.target.value })}>
          {portfolios.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {Object.keys(filters).map((k) => (
          <select key={k} value={filters[k]} className="text-sm" onChange={(e) => setFilters({ ...filters, [k]: e.target.value })}>
            <option value="">{t(`transactions.filters.${k}`)}</option>
            {options[k].map((v) => <option key={v} value={v}>{k === "type" ? t(`transactions.types.${v}`) : v}</option>)}
          </select>
        ))}
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      {portfolioId && <CostSummary portfolioId={portfolioId} method={method} onMethod={changeMethod} symbolFilter={filters.symbol} />}

      <section className="tile overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <tr>
              {["date", "type", "coin", "quantity", "price", "fee", "value", "source"].map((k) => (
                <th key={k} className="px-3 py-2 font-medium">{t(`transactions.columns.${k}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-zinc-500">{t("transactions.empty")}</td></tr>
            )}
            {shown.map((item) => {
              const key = `${item.kind}-${item.id}`;
              return (
                <Fragment key={key}>
                  <tr className="cursor-pointer border-t border-white/[0.04] hover:bg-white/[0.02]" onClick={() => setOpen(open === key ? null : key)}>
                    <td className="whitespace-nowrap px-3 py-2 text-zinc-400">{fmtDateTime(item.occurred_at)}</td>
                    <td className={`px-3 py-2 ${TYPE_TONE[item.type] ?? ""}`}>{t(`transactions.types.${item.type}`)}</td>
                    <td className="px-3 py-2 font-medium text-zinc-100">{item.symbol}</td>
                    <td className="num px-3 py-2">{fmtQty(item.quantity)}</td>
                    <td className="num px-3 py-2">{dash(item.price, fmtUnitPrice)}</td>
                    <td className="num px-3 py-2 text-zinc-400">
                      {Number(item.fee_coin) ? `${fmtQty(item.fee_coin)} ${item.symbol}` : Number(item.fee_quote) ? fmtMoney(item.fee_quote) : "—"}
                    </td>
                    <td className="num px-3 py-2">{dash(item.value, fmtMoney)}</td>
                    <td className="px-3 py-2">
                      <span className="chip">{item.source}</span>
                      {item.missing_in_export && <span className="ml-1 text-amber-300" title={t("transactions.missing")}>⚠</span>}
                      {item.note && <span className="ml-1 text-zinc-500" title={item.note}>✎</span>}
                    </td>
                  </tr>
                  {open === key && (
                    <tr><td colSpan={8} className="p-0"><Details item={item} onSaved={load} /></td></tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
