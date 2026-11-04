import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { importApi } from "../api/endpoints";
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

/** One subfolder of the import folder: ticked ones are synchronized (the choice is remembered). */
function FolderTile({ folder, disabled, onChange }) {
  return (
    <label className={`tile flex cursor-pointer items-start gap-2 p-3 text-sm ${folder.selected ? "" : "opacity-60"}`}>
      <input type="checkbox" className="mt-0.5" checked={folder.selected} disabled={disabled}
        onChange={(event) => onChange(folder.name, event.target.checked)} />
      <span className="min-w-0">
        <span className="block break-all text-zinc-200">{folder.name || t("imports.mainFolder")}</span>
        {folder.portfolio && <span className="block text-xs text-zinc-500">{folder.portfolio}</span>}
        <span className="block text-xs text-zinc-500">
          {t("imports.folderFiles", { count: folder.files })}
          {folder.new > 0 && <span className="text-neon-violet"> · {t("imports.folderNew", { count: folder.new })}</span>}
        </span>
      </span>
    </label>
  );
}

/** One file of a ticked folder - a new one can be picked for the import. */
function FileRow({ file, portfolio, picked, disabled, onToggle }) {
  const name = file.filename.split("/").pop();
  return (
    <tr className={`border-t border-white/[0.04] ${file.status === "unrecognized" ? "opacity-60" : ""}`}>
      <td className="py-2 pr-2">
        {file.status === "new" && (
          <input type="checkbox" checked={picked} disabled={disabled} aria-label={name}
            onChange={() => onToggle(file.filename)} />
        )}
      </td>
      <td className="w-full max-w-0 py-2 pr-3"><span className="block truncate text-zinc-200" title={name}>{name}</span></td>
      <td className="whitespace-nowrap py-2 pr-3 text-xs text-zinc-400">{portfolio}</td>
      <td className="num whitespace-nowrap py-2 pr-3 text-xs text-zinc-400">{fmtDateTime(file.modified)}</td>
      <td className={`whitespace-nowrap py-2 pr-3 text-xs ${STATUS_TONE[file.status]}`}>{t(`imports.status.${file.status}`)}</td>
      <td className="num whitespace-nowrap py-2 text-xs text-zinc-500" title={file.import ? t("imports.counts", {
        total: file.import.rows_total, new: file.import.rows_new, updated: file.import.rows_updated,
        skipped: file.import.rows_skipped, unchanged: file.import.rows_unchanged }) : undefined}>
        {file.import && t("imports.folderNew", { count: file.import.rows_new })}
      </td>
    </tr>
  );
}

/** Import panel: folders to synchronize, their files, target portfolio and flagged entries. */
export default function ImportPage() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [unpicked, setUnpicked] = useState(() => new Set());     // new files the user unticked

  const run = useCallback(async (fn) => {
    setBusy(true);
    setError(null);
    try {
      setStatus(await fn());
      window.dispatchEvent(new Event("portfolios:changed"));   // new / changed import portfolios
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    run(importApi.status);
  }, [run]);

  if (!status) return <p className="text-sm text-zinc-500">{error ?? t("common.loading")}</p>;

  const files = status.files.filter((f) => f.status !== "skipped");
  const importable = files.filter((f) => f.status === "new");
  const picked = importable.filter((f) => !unpicked.has(f.filename)).map((f) => f.filename);
  const portfolioOf = (file) => status.folders.find((f) => f.name === file.folder)?.portfolio ?? file.folder;
  const toggleFile = (filename) => setUnpicked((old) => {
    const next = new Set(old);
    if (!next.delete(filename)) next.add(filename);
    return next;
  });
  const toggleAll = () => setUnpicked(new Set(picked.length === importable.length ? importable.map((f) => f.filename) : []));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">{t("imports.title")}</h1>
          <p className="text-xs text-zinc-500">{t("imports.intro")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-ghost" disabled={busy} title={t("imports.reprocessHint")}
            onClick={() => run(importApi.reprocess)}>
            {t("imports.reprocess")}
          </button>
          <button type="button" className="btn-primary" disabled={busy || picked.length === 0}
            onClick={() => run(() => importApi.sync(picked))}>
            {busy ? t("imports.syncing") : t("imports.sync", { count: picked.length })}
          </button>
        </div>
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      <section className="tile space-y-3 p-4">
        <div className="text-sm text-zinc-400">
          {t("imports.folder")}: <code className="break-all text-zinc-200">{status.folder}</code>
        </div>
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("imports.folders")}</h2>
          <p className="text-xs text-zinc-500">{t("imports.foldersHint")}</p>
        </div>
        {status.folders.length === 0 && <p className="text-sm text-zinc-500">{t("imports.noFolders")}</p>}
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {status.folders.map((f) => (
            <FolderTile key={f.name} folder={f} disabled={busy}
              onChange={(name, selected) => run(() => importApi.selectFolder(name, selected))} />
          ))}
        </div>
        <p className="text-xs text-zinc-500">{t("imports.portfolioHint")}</p>
        {status.portfolios.length > 0 && (
          <ul className="flex flex-wrap gap-3 text-sm">
            {status.portfolios.map((p) => (
              <li key={p.id}>
                <Link to={`/transactions?portfolio=${p.id}`} className="text-neon-blue hover:underline">
                  {t("imports.openDetails", { name: p.name })}
                </Link>
              </li>
            ))}
          </ul>
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
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("imports.files")}</h2>
        <p className="mb-2 text-xs text-zinc-500">{t("imports.filesHint")}</p>
        {files.length === 0 && <p className="text-sm text-zinc-500">{t("imports.noFiles")}</p>}
        {files.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[38rem] text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500">
                  <th className="pb-2 pr-2 font-normal">
                    {importable.length > 0 && (
                      <input type="checkbox" checked={picked.length === importable.length} disabled={busy}
                        aria-label={t("imports.pickAll")} title={t("imports.pickAll")} onChange={toggleAll} />
                    )}
                  </th>
                  <th className="pb-2 pr-3 font-normal">{t("imports.columns.file")}</th>
                  <th className="pb-2 pr-3 font-normal">{t("imports.columns.account")}</th>
                  <th className="pb-2 pr-3 font-normal">{t("imports.columns.date")}</th>
                  <th className="pb-2 pr-3 font-normal">{t("imports.columns.status")}</th>
                  <th className="pb-2 font-normal">{t("imports.columns.rows")}</th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <FileRow key={f.filename} file={f} portfolio={portfolioOf(f)} disabled={busy}
                    picked={picked.includes(f.filename)} onToggle={toggleFile} />
                ))}
              </tbody>
            </table>
          </div>
        )}
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

      <details className="tile p-4">
        <summary className="cursor-pointer text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("imports.history")}</summary>
        {status.history.length === 0 && <p className="text-sm text-zinc-500">{t("imports.noHistory")}</p>}
        <ul className="mt-2 divide-y divide-white/[0.04]">
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
      </details>
    </div>
  );
}
