import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { alertsApi, indicatorsApi } from "../api/endpoints";
import CoinPicker from "../components/CoinPicker";
import { ErrorBanner } from "../components/ui";
import { t } from "../i18n";
import { conditionText, operandLabel } from "../lib/alertText";
import { SOURCES, alertOutputs, defaultParams, outputLabel, paramLabel } from "../lib/indicatorMeta";
import ParamFields from "../components/chart/ParamFields";
import { fmtDateTime, fmtPrice } from "../lib/format";
import { intervalLabel, intervalOptions } from "../lib/intervals";
import { useChartIntervals } from "../lib/useChartIntervals";

const TRIGGERS = ["intrabar", "bar_open", "bar_close"];
const OPERATORS = [">", "<", ">=", "<=", "==", "crosses_above", "crosses_below"];
const changed = () => window.dispatchEvent(new Event("alerts:changed"));

function defaultOperand(type, definitions) {
  if (type === "price") return { type: "price" };
  if (type === "value") return { type: "value", value: "" };
  const def = definitions.find((d) => d.id === "rsi") ?? definitions[0];
  return { type: "indicator", id: def.id, params: defaultParams(def), output: alertOutputs(def)[0].name };
}

/** One side of a condition: price, a fixed value or an indicator output with parameters. */
function OperandEditor({ operand, onChange, definitions }) {
  const def = operand.type === "indicator" ? definitions.find((d) => d.id === operand.id) : null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <select value={operand.type} onChange={(e) => onChange(defaultOperand(e.target.value, definitions))} className="text-sm">
        {["price", "value", "indicator"].map((type) => <option key={type} value={type}>{t(`alerts.operandTypes.${type}`)}</option>)}
      </select>
      {operand.type === "value" && (
        <input type="text" inputMode="decimal" className="w-28 text-sm" value={operand.value}
          onChange={(e) => onChange({ ...operand, value: e.target.value })} />
      )}
      {def && (
        <>
          <select value={operand.id} className="text-sm"
            onChange={(e) => onChange({ ...defaultOperand("indicator", definitions.filter((d) => d.id === e.target.value)) })}>
            {definitions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          {def.params.some((p) => p.group) ? (
            <details className="w-full">
              <summary className="cursor-pointer text-xs text-zinc-400">{t("alerts.form.settings", { count: def.params.length })}</summary>
              <div className="mt-2">
                <ParamFields def={def} params={operand.params} idPrefix={`alert-${def.id}`}
                  onChange={(params) => onChange({ ...operand, params })} />
              </div>
            </details>
          ) : def.params.map((p) => (
            <label key={p.name} className="flex items-center gap-1 text-xs text-zinc-500">
              {paramLabel(def, p)}
              {p.type === "source" ? (
                <select className="py-1 text-xs" value={operand.params[p.name]}
                  onChange={(e) => onChange({ ...operand, params: { ...operand.params, [p.name]: e.target.value } })}>
                  {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              ) : (
                <input type="number" className="w-16 py-1 text-xs" value={operand.params[p.name]} step={p.type === "int" ? 1 : "any"}
                  onChange={(e) => onChange({ ...operand, params: { ...operand.params, [p.name]: e.target.value } })} />
              )}
            </label>
          ))}
          {alertOutputs(def).length > 1 && (
            <select value={operand.output} className="text-sm" onChange={(e) => onChange({ ...operand, output: e.target.value })}>
              {alertOutputs(def).map((o) => <option key={o.name} value={o.name}>{outputLabel(def, o)}</option>)}
            </select>
          )}
        </>
      )}
    </div>
  );
}

function NewAlertForm({ definitions, onCreated }) {
  const [form, setForm] = useState({
    symbol: "BTC", interval: "1h", mode: "once", trigger: "bar_close", note: "",
    left: { type: "price" }, op: ">", right: { type: "value", value: "" },
  });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [intervals] = useChartIntervals();
  const set = (changes) => setForm((f) => ({ ...f, ...changes }));

  const toApi = (operand) => {
    if (operand.type !== "value") return operand;
    return { type: "value", value: Number(String(operand.value).replace(",", ".")) };
  };

  const submit = async (e) => {
    e.preventDefault();
    const condition = { left: toApi(form.left), op: form.op, right: toApi(form.right) };
    if ([condition.left, condition.right].some((o) => o.type === "value" && !Number.isFinite(o.value))) {
      return setError(t("alerts.form.invalidValue"));
    }
    setBusy(true);
    setError(null);
    try {
      await alertsApi.create({ symbol: form.symbol, interval: form.interval, condition, mode: form.mode,
        trigger: form.trigger, note: form.note.trim() || null });
      onCreated();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="tile space-y-3 p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("alerts.form.title")}</h2>
      <div className="flex flex-wrap items-end gap-3">
        <label className="w-48">
          <span className="label">{t("alerts.form.symbol")}</span>
          <CoinPicker value={form.symbol} onChange={(s) => s && set({ symbol: s })} />
        </label>
        <label>
          <span className="label">{t("alerts.form.interval")}</span>
          <select value={form.interval} onChange={(e) => set({ interval: e.target.value })} className="text-sm">
            {intervalOptions(intervals, form.interval).map((i) => <option key={i} value={i}>{intervalLabel(i)}</option>)}
          </select>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-zinc-500">{t("alerts.form.when")}</span>
        <OperandEditor operand={form.left} onChange={(left) => set({ left })} definitions={definitions} />
        <select value={form.op} onChange={(e) => set({ op: e.target.value })} className="text-sm">
          {OPERATORS.map((op) => <option key={op} value={op}>{t(`alerts.operators.${op}`)}</option>)}
        </select>
        <OperandEditor operand={form.right} onChange={(right) => set({ right })} definitions={definitions} />
      </div>
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <select value={form.mode} onChange={(e) => set({ mode: e.target.value })} className="text-sm">
          {["once", "repeat"].map((m) => <option key={m} value={m}>{t(`alerts.form.modes.${m}`)}</option>)}
        </select>
        <label className="flex items-center gap-2 text-zinc-400">
          {t("alerts.form.trigger")}
          <select value={form.trigger} onChange={(e) => set({ trigger: e.target.value })} className="text-sm">
            {TRIGGERS.map((tr) => <option key={tr} value={tr}>{t(`alerts.triggers.${tr}.label`)}</option>)}
          </select>
        </label>
      </div>
      <p className="text-xs text-zinc-500">{t(`alerts.triggers.${form.trigger}.hint`)}</p>
      <input className="w-full text-sm" placeholder={t("alerts.form.note")} maxLength={500} value={form.note}
        onChange={(e) => set({ note: e.target.value })} />
      {error && <p className="text-sm text-loss">{error}</p>}
      <button type="submit" className="btn-primary" disabled={busy || !definitions.length}>{t("alerts.form.submit")}</button>
    </form>
  );
}

function AlertRow({ alert, definitions, onChanged }) {
  const [check, setCheck] = useState(null);
  const [error, setError] = useState(null);
  const run = (fn) => fn().then(onChanged).catch((err) => setError(errorMessage(err)));
  const fmt = (v) => (v === null || v === undefined ? "—" : fmtPrice(v));

  return (
    <li className="space-y-1 border-t border-white/[0.04] py-2.5 first:border-0">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
        <span className="font-semibold text-zinc-100">{alert.symbol}</span>
        <span className="chip">{intervalLabel(alert.interval)}</span>
        <span className="text-zinc-200">{conditionText(alert.condition, definitions)}</span>
        <span className={`chip ${alert.active ? "text-profit" : ""}`}>{alert.active ? t("alerts.list.active") : t("alerts.list.inactive")}</span>
        <select value={alert.trigger} title={t(`alerts.triggers.${alert.trigger}.hint`)}
          onChange={(e) => run(() => alertsApi.update(alert.id, { trigger: e.target.value }))}
          className="py-0.5 text-[11px] text-zinc-400">
          {TRIGGERS.map((tr) => <option key={tr} value={tr}>{t(`alerts.triggers.${tr}.short`)}</option>)}
        </select>
        {alert.last_triggered_at && (
          <span className="text-xs text-zinc-500">{t("alerts.list.lastTriggered", { date: fmtDateTime(`${alert.last_triggered_at}Z`) })}</span>
        )}
        <span className="ml-auto flex gap-2 text-xs">
          <button type="button" className="text-neon-green hover:underline"
            onClick={() => alertsApi.check(alert.id).then(setCheck).catch((err) => setError(errorMessage(err)))}>
            {t("alerts.list.check")}
          </button>
          <button type="button" className="text-zinc-300 hover:underline"
            onClick={() => run(() => alertsApi.update(alert.id, { active: !alert.active }))}>
            {alert.active ? t("alerts.list.deactivate") : t("alerts.list.activate")}
          </button>
          <button type="button" className="text-loss hover:underline" onClick={() => run(() => alertsApi.remove(alert.id))}>
            {t("alerts.list.delete")}
          </button>
        </span>
      </div>
      {alert.note && <p className="text-xs text-zinc-500">{alert.note}</p>}
      {check && (
        <p className="num text-xs text-zinc-400">
          {operandLabel(alert.condition.left, definitions)}: {fmt(check.left)} · {operandLabel(alert.condition.right, definitions)}: {fmt(check.right)}
          {" → "}<span className={check.met ? "text-profit" : "text-zinc-300"}>{check.met ? t("alerts.list.met") : t("alerts.list.notMet")}</span>
        </p>
      )}
      {error && <p className="text-xs text-loss">{error}</p>}
    </li>
  );
}

function NotificationButton() {
  const supported = typeof Notification !== "undefined";
  const [permission, setPermission] = useState(supported ? Notification.permission : "denied");
  if (!supported) return null;
  if (permission === "granted") return <span className="text-xs text-profit">{t("alerts.notificationsOn")}</span>;
  if (permission === "denied") return <span className="text-xs text-zinc-500">{t("alerts.notificationsBlocked")}</span>;
  return (
    <button type="button" className="btn-ghost text-xs" onClick={() => Notification.requestPermission().then(setPermission)}>
      {t("alerts.enableNotifications")}
    </button>
  );
}

export default function AlertsPage() {
  const [definitions, setDefinitions] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    Promise.all([alertsApi.list(), alertsApi.events({ unseenOnly: false })])
      .then(([a, e]) => {
        setAlerts(a);
        setEvents(e);
      })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    indicatorsApi.list().then(setDefinitions).catch(() => {});
    load();
  }, [load]);

  const markAllSeen = async () => {
    await alertsApi.markSeen();
    changed();
    load();
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">{t("alerts.title")}</h1>
          <p className="max-w-2xl text-xs text-zinc-500">{t("alerts.intro")}</p>
        </div>
        <NotificationButton />
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      <NewAlertForm definitions={definitions} onCreated={load} />

      <section className="tile p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("alerts.list.title")}</h2>
        {alerts.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">{t("alerts.list.empty")}</p>
        ) : (
          <ul className="mt-2">{alerts.map((a) => <AlertRow key={a.id} alert={a} definitions={definitions} onChanged={load} />)}</ul>
        )}
      </section>

      <section className="tile p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{t("alerts.events.title")}</h2>
          {events.some((e) => !e.seen) && (
            <button type="button" className="text-xs text-neon-green hover:underline" onClick={markAllSeen}>{t("alerts.events.markAllSeen")}</button>
          )}
        </div>
        {events.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">{t("alerts.events.empty")}</p>
        ) : (
          <ul className="mt-2 divide-y divide-white/[0.04] text-sm">
            {events.map((e) => (
              <li key={e.id} className="flex flex-wrap items-baseline gap-x-3 py-1.5">
                <span className="text-zinc-400">{fmtDateTime(`${e.triggered_at}Z`)}</span>
                <span className="font-semibold text-zinc-100">{e.symbol}</span>
                <span className="text-zinc-200">{conditionText(e.condition, definitions)}</span>
                <span className="num text-xs text-zinc-500">
                  {t("alerts.events.values", { left: fmtPrice(e.details.left), right: fmtPrice(e.details.right), price: fmtPrice(e.details.price) })}
                </span>
                {!e.seen && <span className="chip text-neon-green">{t("alerts.events.new")}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
