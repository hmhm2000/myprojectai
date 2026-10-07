import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../../api/client";
import { t } from "../../i18n";
import { PRESET_INTERVALS, intervalLabel, parseInterval } from "../../lib/intervals";
import { useChartIntervals } from "../../lib/useChartIntervals";
import { ChevronIcon, TrashIcon } from "../icons";

/**
 * Interval buttons above the chart (the pinned ones) and a drop-down menu with all intervals:
 * a checkbox pins/unpins each one, custom intervals (3D, 2W ...) can be added and removed.
 * Everything is saved on the server for the user.
 */
export default function IntervalPicker({ value, onChange }) {
  const [intervals, actions] = useChartIntervals();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const menuRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => !menuRef.current?.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const list = intervals ?? PRESET_INTERVALS.map((name) => ({ name, custom: false, pinned: true }));
  const buttons = list.filter((i) => i.pinned || i.name === value).map((i) => i.name);
  if (!buttons.includes(value)) buttons.push(value);

  const run = async (fn) => {
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const submit = (e) => {
    e.preventDefault();
    const name = parseInterval(text);
    if (!name) {
      setError(t("chart.customInterval.invalid"));
      return;
    }
    run(async () => {
      await actions.add(name);
      setText("");
      setOpen(false);
      onChange(name);
    });
  };

  return (
    <div className="flex flex-wrap items-center gap-1">
      {buttons.map((name) => (
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
      ))}

      <div ref={menuRef} className="relative">
        <button
          type="button"
          title={t("chart.customInterval.menu")}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
          className="btn-icon h-7 w-7"
        >
          <ChevronIcon size={14} />
        </button>
        {open && (
          <div className="tile absolute left-0 top-9 z-30 w-60 space-y-2 p-3 shadow-xl">
            <p className="text-xs text-zinc-500">{t("chart.customInterval.menuHint")}</p>
            <ul className="max-h-72 space-y-0.5 overflow-y-auto">
              {list.map((i) => (
                <li key={i.name} className="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-white/5">
                  <input
                    type="checkbox"
                    checked={i.pinned}
                    title={t("chart.customInterval.pin")}
                    onChange={(e) => run(() => actions.setPinned(i.name, e.target.checked))}
                  />
                  <button type="button" className="flex-1 text-left text-sm text-zinc-200"
                    onClick={() => { onChange(i.name); setOpen(false); }}>
                    {intervalLabel(i.name)}
                    {i.custom && <span className="ml-2 text-[10px] text-zinc-500">{t("chart.customInterval.own")}</span>}
                  </button>
                  {i.custom && (
                    <button type="button" className="text-zinc-500 hover:text-loss" title={t("chart.customInterval.remove")}
                      onClick={() => run(() => actions.remove(i.name))}>
                      <TrashIcon size={12} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <form onSubmit={submit} className="flex items-center gap-1 border-t border-white/[0.05] pt-2">
              <input
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  setError("");
                }}
                placeholder={t("chart.customInterval.placeholder")}
                title={t("chart.customInterval.hint")}
                className="w-full py-1 text-xs"
              />
              <button type="submit" className="btn-ghost px-2 py-1 text-xs">{t("chart.customInterval.add")}</button>
            </form>
            <p className="text-[11px] text-zinc-500">{t("chart.customInterval.hint")}</p>
            {error && <p className="text-xs text-loss">{error}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
