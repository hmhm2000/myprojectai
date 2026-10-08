import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { importApi, portfoliosApi } from "../api/endpoints";
import { ErrorBanner } from "../components/ui";
import { hasTranslation, t } from "../i18n";
import { fmtDateTime, fmtQty, fmtUnitPrice } from "../lib/format";

const STATUS_TONE = { imported: "text-profit", new: "text-neon-violet", already_imported: "text-zinc-400",
  unrecognized: "text-amber-300", error: "text-loss" };

/** "Sale without purchases: 1.02 DOGE ..." - translated warning of an import. */
function warningText(warning) {
  const key = `imports.warnings.${warning.code}`;
  return hasTranslation(key) ? t(key, warning.params ?? {}) : `${warning.code} ${JSON.stringify(warning.params ?? {})}`;
}

function Counts({ row }) {
  return (
    <span className="num text-xs text-zinc-400">
      {t("imports.counts", { total: row.rows_total, new: row.rows_new, updated: row.rows_updated,
        skipped: row.rows_skipped, unchanged: row.rows_unchanged })}
    </span>
  );
}

function Warnings({ warnings }) {
  const problems = warnings.filter((w) => w.code !== "balance_ok");
  const balances = warnings.filter((w) => w.code.startsWith("balance_"));
  if (!warnings.length) return null;
  return (
    <div className="mt-2 space-y-2">
      {problems.length > 0 && (
        <ul className="space-y-1 text-xs text-amber-200">
          {problems.map((w, i) => <li key={i}>⚠ {warningText(w)}</li>)}
        </ul>
      )}
      {balances.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {balances.map((w) => (
            <span key={w.params.coin} title={t("imports.balanceTitle", w.params)}
              className={`chip num ${w.code === "balance_ok" ? "text-profit" : "text-loss"}`}>
              {w.params.coin} {w.code === "balance_ok" ? "✓" : "≠"}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Import panel: export files in the folder, "Synchronizuj", target portfolio and flagged entries. */
export default function ImportPage() {
  const [status, setStatus] = useState(null);
  const [portfolios, setPortfolios] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const run = useCallback(async (fn) => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await fn());
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    run(importApi.status);
    portfoliosApi.list().then(setPortfolios).catch(() => {});
  }, [run]);

  if (!status) return <p className="text-sm text-zinc-500">{error ?? t("common.loading")}</p>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">{t("imports.title")}</h1>
          <p className="text-xs text-zinc-500">{t("imports.intro")}</p>
        </div>
        <button type="button" className="btn-primary" disabled={busy} onClick={() => run(importApi.sync)}>
          {busy ? t("imports.syncing") : t("imports.sync")}
        </button>
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      <section className="tile space-y-3 p-4">
        <div className="text-sm text-zinc-400">
          {t("imports.folder")}: <code className="break-all text-zinc-200">{status.folder}</code>
        </div>
        <label className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
          {t("imports.portfolio")}
          <select value={status.portfolio_id ?? ""} className="text-sm"
            onChange={(e) => run(() => importApi.settings({ portfolio_id: Number(e.target.value) }))}>
            {status.portfolio_id === null && <option value="">{t("imports.portfolioAuto")}</option>}
            {portfolios.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <span className="text-xs text-zinc-500">{t("imports.portfolioHint")}</span>
        </label>
        {status.portfolio_id && (
          <Link to={`/transactions?portfolio=${status.portfolio_id}`} className="text-sm text-neon-green hover:underline">
            {t("imports.openDetails")}
          </Link>
        )}
      </section>

      {status.last_sync.length > 0 && (
        <section className="tile p-4">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("imports.lastSync")}</h2>
          <ul className="space-y-2">
            {status.last_sync.map((r) => (
              <li key={r.filename} className="text-sm">
                <span className="break-all text-zinc-200">{r.filename}</span>{" "}
                <span className={STATUS_TONE[r.status]}>{t(`imports.status.${r.status}`)}</span>
                {r.status === "imported" && <> · <Counts row={r} /></>}
                {r.message && <span className="text-xs text-loss"> {r.message}</span>}
                {r.status === "imported" && <Warnings warnings={r.warnings} />}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="tile p-4">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("imports.files")}</h2>
        {status.files.length === 0 && <p className="text-sm text-zinc-500">{t("imports.noFiles")}</p>}
        <ul className="divide-y divide-white/[0.04]">
          {status.files.map((f) => (
            <li key={f.filename} className="py-2 text-sm">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span className="break-all text-zinc-200">{f.filename}</span>
                <span className={STATUS_TONE[f.status]}>{t(`imports.status.${f.status}`)}</span>
                {f.import && <span className="text-xs text-zinc-500">{fmtDateTime(`${f.import.imported_at}Z`)}</span>}
              </div>
              {f.import && <Counts row={f.import} />}
            </li>
          ))}
        </ul>
      </section>

      <section className="tile p-4">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("imports.missing.title")}</h2>
        <p className="mb-2 text-xs text-zinc-500">{t("imports.missing.hint")}</p>
        {status.missing.length === 0 && <p className="text-sm text-zinc-500">{t("imports.missing.none")}</p>}
        <ul className="divide-y divide-white/[0.04]">
          {status.missing.map((m) => (
            <li key={`${m.kind}-${m.id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 text-sm">
              <span className="chip">{t(`transactions.types.${m.type}`)}</span>
              <span className="text-zinc-200">{m.symbol}</span>
              <span className="num text-zinc-400">{fmtQty(m.quantity)}</span>
              {m.price && <span className="num text-zinc-400">@ {fmtUnitPrice(m.price)}</span>}
              <span className="text-xs text-zinc-500">{fmtDateTime(m.occurred_at)} · {m.source} {m.external_id}</span>
              <span className="ml-auto flex gap-3 text-xs">
                <button type="button" className="text-zinc-300 hover:underline" disabled={busy}
                  onClick={() => run(() => importApi.keep(m.kind, m.id))}>{t("imports.missing.keep")}</button>
                <button type="button" className="text-loss hover:underline" disabled={busy}
                  onClick={() => window.confirm(t("imports.missing.confirmDelete")) && run(() => importApi.remove(m.kind, m.id))}>
                  {t("imports.missing.delete")}
                </button>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="tile p-4">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("imports.history")}</h2>
        {status.history.length === 0 && <p className="text-sm text-zinc-500">{t("imports.noHistory")}</p>}
        <ul className="divide-y divide-white/[0.04]">
          {status.history.map((h) => (
            <li key={h.id} className="py-2 text-sm">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span className="break-all text-zinc-200">{h.filename}</span>
                <span className="text-xs text-zinc-500">{h.source} · {fmtDateTime(`${h.imported_at}Z`)}</span>
              </div>
              <Counts row={h} />
              <Warnings warnings={h.warnings} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
