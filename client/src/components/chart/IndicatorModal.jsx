import { useState } from "react";
import { errorMessage } from "../../api/client";
import { hasTranslation, t } from "../../i18n";
import Modal from "../Modal";
import { Field } from "../ui";
import { intervalLabel, intervalOptions } from "../../lib/intervals";

const SOURCES = ["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"];
const paramLabel = (name) => (hasTranslation(`chart.params.${name}`) ? t(`chart.params.${name}`) : name);
const defaults = (def) => Object.fromEntries(def.params.map((p) => [p.name, p.default]));

/**
 * Add / edit one chart indicator. The fields come from the indicator definition (backend), so every
 * indicator gets its own settings; plus the timeframe it is computed on ("" = follow the chart).
 * `item` = saved settings (edit) or null (add). onSave({ indicator_id, params, interval }).
 */
export default function IndicatorModal({ definitions, item = null, onSave, onReset, onClose }) {
  const editing = Boolean(item);
  const [indicatorId, setIndicatorId] = useState(item?.indicator_id ?? definitions[0]?.id ?? "");
  const def = definitions.find((d) => d.id === indicatorId);
  const [params, setParams] = useState(item?.params ?? (def ? defaults(def) : {}));
  const [interval, setInterval] = useState(item?.interval ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const choose = (id) => {
    setIndicatorId(id);
    const next = definitions.find((d) => d.id === id);
    setParams(next ? defaults(next) : {});
  };

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    run(() => onSave({ indicator_id: indicatorId, params, interval: interval || null }));
  };

  return (
    <Modal title={editing ? t("chart.indicators.editTitle", { name: def?.name ?? "" }) : t("chart.indicators.addTitle")} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {!editing && (
          <Field label={t("chart.indicators.indicator")} htmlFor="ind-id">
            <select id="ind-id" className="w-full" value={indicatorId} onChange={(e) => choose(e.target.value)}>
              {definitions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
        )}
        {def?.description && <p className="text-xs text-zinc-500">{def.description}</p>}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {def?.params.map((p) => (
            <Field key={p.name} label={paramLabel(p.name)} htmlFor={`ind-${p.name}`}>
              {p.type === "source" ? (
                <select id={`ind-${p.name}`} className="w-full" value={params[p.name] ?? p.default}
                  onChange={(e) => setParams({ ...params, [p.name]: e.target.value })}>
                  {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              ) : (
                <input id={`ind-${p.name}`} type="number" className="w-full" value={params[p.name] ?? p.default}
                  step={p.type === "int" ? 1 : "any"} min={p.min ?? undefined} max={p.max ?? undefined}
                  onChange={(e) => setParams({ ...params, [p.name]: e.target.value })} required />
              )}
            </Field>
          ))}
          <Field label={t("chart.indicators.interval")} htmlFor="ind-interval" hint={t("chart.indicators.intervalHint")}>
            <select id="ind-interval" className="w-full" value={interval} onChange={(e) => setInterval(e.target.value)}>
              <option value="">{t("chart.indicators.followChart")}</option>
              {intervalOptions(interval).map((i) => <option key={i} value={i}>{intervalLabel(i)}</option>)}
            </select>
          </Field>
        </div>

        {error && <p className="text-sm text-loss">{error}</p>}
        <div className="flex flex-wrap justify-end gap-2">
          {editing && onReset && (
            <button type="button" className="btn-ghost mr-auto" disabled={busy} onClick={() => run(onReset)}>
              {t("chart.indicators.reset")}
            </button>
          )}
          <button type="button" className="btn-ghost" onClick={onClose}>{t("common.actions.cancel")}</button>
          <button type="submit" className="btn-primary" disabled={busy || !def}>
            {busy ? t("common.actions.saving") : t("common.actions.save")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
