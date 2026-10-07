import { useState } from "react";
import { t } from "../../i18n";
import {
  PRESET_INTERVALS, customIntervals, forgetCustomInterval, intervalLabel, parseInterval, rememberCustomInterval,
} from "../../lib/intervals";

/** Interval buttons (1m ... 1M), remembered custom intervals and a field to type a new one (e.g. 3D, 2W). */
export default function IntervalPicker({ value, onChange }) {
  const [customs, setCustoms] = useState(customIntervals);
  const [text, setText] = useState("");
  const [invalid, setInvalid] = useState(false);

  const shown = [...customs];
  if (!PRESET_INTERVALS.includes(value) && !shown.includes(value)) shown.unshift(value);

  const submit = (e) => {
    e.preventDefault();
    const name = parseInterval(text);
    if (!name) {
      setInvalid(true);
      return;
    }
    rememberCustomInterval(name);
    setCustoms(customIntervals());
    setText("");
    setInvalid(false);
    onChange(name);
  };

  const forget = (name) => {
    forgetCustomInterval(name);
    setCustoms(customIntervals());
  };

  const button = (name) => (
    <button
      key={name}
      type="button"
      onClick={() => onChange(name)}
      className={`rounded-lg px-2.5 py-1.5 text-xs transition ${
        name === value ? "bg-neon-violet/20 text-zinc-50" : "text-zinc-400 hover:bg-white/5"
      }`}
    >
      {intervalLabel(name)}
    </button>
  );

  return (
    <div className="flex flex-wrap items-center gap-1">
      {PRESET_INTERVALS.map(button)}
      {shown.map((name) => (
        <span key={name} className="group relative flex items-center">
          {button(name)}
          {customs.includes(name) && (
            <button
              type="button"
              title={t("chart.customInterval.remove")}
              onClick={() => forget(name)}
              className="ml-0.5 hidden rounded px-1 text-[10px] text-zinc-500 hover:text-loss group-hover:block"
            >
              ×
            </button>
          )}
        </span>
      ))}
      <form onSubmit={submit} className="ml-1 flex items-center gap-1">
        <input
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setInvalid(false);
          }}
          placeholder={t("chart.customInterval.placeholder")}
          title={invalid ? t("chart.customInterval.invalid") : t("chart.customInterval.hint")}
          className={`w-20 py-1 text-xs ${invalid ? "border-loss" : ""}`}
        />
        <button type="submit" className="btn-ghost px-2 py-1 text-xs">{t("chart.customInterval.add")}</button>
      </form>
      {invalid && <span className="text-xs text-loss">{t("chart.customInterval.invalid")}</span>}
    </div>
  );
}
