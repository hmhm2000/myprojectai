import { useState } from "react";
import { errorMessage } from "../api/client";
import { maintenanceApi } from "../api/endpoints";
import { t } from "../i18n";
import { ErrorBanner } from "./ui";

/**
 * One-off cleanup of manual portfolios (everything except SPX): first a dry run with the counts,
 * then removal only after typing the confirmation word. A backup is written before removing.
 */
export default function ManualCleanup() {
  const [plan, setPlan] = useState(null);
  const [typed, setTyped] = useState("");
  const [deleteEmpty, setDeleteEmpty] = useState(false);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const word = t("settings.cleanup.confirmWord");

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const check = () => run(async () => {
    setResult(null);
    setTyped("");
    setPlan(await maintenanceApi.cleanupPlan());
  });

  const execute = () => run(async () => {
    const done = await maintenanceApi.cleanup({ confirm: true, positions: plan.positions, sales: plan.sales,
      delete_empty_portfolios: deleteEmpty });
    setResult(done);
    setPlan(null);
    window.dispatchEvent(new Event("portfolios:changed"));
  });

  return (
    <div className="space-y-3 text-sm">
      <p className="text-zinc-400">{t("settings.cleanup.intro", { symbols: "SPX" })}</p>
      <button type="button" className="btn-ghost" disabled={busy} onClick={check}>{t("settings.cleanup.dryRun")}</button>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      {plan && (
        <div className="space-y-3 rounded-lg border border-white/[0.06] p-3">
          <p className="text-zinc-200">
            {t("settings.cleanup.summary", { positions: plan.positions, sales: plan.sales,
              keptPositions: plan.kept_positions, keptSales: plan.kept_sales })}
          </p>
          <ul className="space-y-1 text-xs text-zinc-400">
            {plan.portfolios.map((p) => (
              <li key={p.id}>
                {t("settings.cleanup.portfolio", { name: p.name, positions: p.positions, sales: p.sales,
                  kept: p.kept_positions })}
                {p.symbols.length > 0 && <span className="text-zinc-500"> ({p.symbols.join(", ")})</span>}
              </li>
            ))}
          </ul>
          {plan.positions + plan.sales + plan.movements === 0 ? (
            <p className="text-xs text-zinc-500">{t("settings.cleanup.nothing")}</p>
          ) : (
            <>
              <label className="flex items-center gap-2 text-xs text-zinc-400">
                <input type="checkbox" checked={deleteEmpty} onChange={(e) => setDeleteEmpty(e.target.checked)} />
                {t("settings.cleanup.deleteEmpty")}
              </label>
              <label className="block text-xs text-zinc-400">
                {t("settings.cleanup.typeToConfirm", { word })}
                <input className="mt-1 block w-40 text-sm" value={typed} onChange={(e) => setTyped(e.target.value)} />
              </label>
              <button type="button" className="btn-primary bg-loss" disabled={busy || typed.trim() !== word} onClick={execute}>
                {t("settings.cleanup.execute", { positions: plan.positions, sales: plan.sales })}
              </button>
            </>
          )}
        </div>
      )}

      {result && (
        <p className="text-xs text-profit">
          {t("settings.cleanup.done", { positions: result.positions, sales: result.sales, backup: result.backup })}
          {result.removed_portfolios.length > 0 && ` ${t("settings.cleanup.removedPortfolios", { names: result.removed_portfolios.join(", ") })}`}
        </p>
      )}
    </div>
  );
}
