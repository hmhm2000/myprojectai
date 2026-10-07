import { useState } from "react";
import { hasTranslation, t } from "../../i18n";
import { CloseIcon, PlusIcon } from "../icons";

const SOURCES = ["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"];
const paramLabel = (name) => (hasTranslation(`chart.params.${name}`) ? t(`chart.params.${name}`) : name);

/** Text like "RSI(14)" or "BB(20, 2)" for an active indicator. */
function indicatorLabel(def, params) {
  const values = def.params.filter((p) => p.type !== "source" || params[p.name] !== "close").map((p) => params[p.name]);
  return `${def.name}(${values.join(", ")})`;
}

/** Active indicators (with remove buttons) + a small form to add one with its parameters. */
export default function IndicatorPanel({ definitions, active, onChange }) {
  const [adding, setAdding] = useState(null); // { id, params }

  const start = (id) => {
    const def = definitions.find((d) => d.id === id);
    setAdding(def ? { id, params: Object.fromEntries(def.params.map((p) => [p.name, p.default])) } : null);
  };
  const addingDef = adding && definitions.find((d) => d.id === adding.id);

  const add = (e) => {
    e.preventDefault();
    onChange([...active, { uid: `${adding.id}-${Date.now()}`, id: adding.id, params: adding.params }]);
    setAdding(null);
  };

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      {active.map((item) => {
        const def = definitions.find((d) => d.id === item.id);
        if (!def) return null;
        return (
          <span key={item.uid} className="chip gap-1.5 py-1 text-zinc-200">
            {indicatorLabel(def, item.params)}
            <button type="button" className="text-zinc-500 hover:text-loss" aria-label={t("chart.indicators.remove")}
              onClick={() => onChange(active.filter((x) => x.uid !== item.uid))}>
              <CloseIcon size={12} />
            </button>
          </span>
        );
      })}

      {!adding ? (
        <select className="py-1 text-xs" value="" onChange={(e) => start(e.target.value)}>
          <option value="">{t("chart.indicators.add")}</option>
          {definitions.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
      ) : (
        <form onSubmit={add} className="flex flex-wrap items-center gap-2 rounded-lg border border-white/10 px-2 py-1">
          <span className="font-medium text-zinc-200">{addingDef.name}</span>
          {addingDef.params.map((p) => (
            <label key={p.name} className="flex items-center gap-1 text-zinc-500">
              {paramLabel(p.name)}
              {p.type === "source" ? (
                <select className="py-0.5 text-xs" value={adding.params[p.name]}
                  onChange={(e) => setAdding({ ...adding, params: { ...adding.params, [p.name]: e.target.value } })}>
                  {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              ) : (
                <input type="number" className="w-16 py-0.5 text-xs" value={adding.params[p.name]}
                  step={p.type === "int" ? 1 : "any"} min={p.min ?? undefined} max={p.max ?? undefined}
                  onChange={(e) => setAdding({ ...adding, params: { ...adding.params, [p.name]: e.target.value } })} />
              )}
            </label>
          ))}
          <button type="submit" className="btn-ghost px-2 py-0.5 text-xs"><PlusIcon size={12} /> {t("chart.indicators.confirm")}</button>
          <button type="button" className="text-zinc-500 hover:text-zinc-200" onClick={() => setAdding(null)}>
            {t("common.actions.cancel")}
          </button>
        </form>
      )}
    </div>
  );
}
