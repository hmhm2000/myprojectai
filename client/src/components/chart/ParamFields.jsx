import { t } from "../../i18n";
import { SOURCES, groupLabel, paramLabel } from "../../lib/indicatorMeta";
import { intervalLabel, intervalOptions } from "../../lib/intervals";
import { useChartIntervals } from "../../lib/useChartIntervals";

/** Color parameter: color picker + opacity (stored as "#rrggbbaa", like Pine color.new(c, transp)). */
function ColorInput({ id, value, onChange }) {
  const rgb = value.slice(0, 7);
  const alpha = value.length === 9 ? parseInt(value.slice(7, 9), 16) : 255;
  const opacity = Math.round((alpha / 255) * 100);
  const set = (nextRgb, nextOpacity) => {
    const a = Math.round((nextOpacity / 100) * 255);
    onChange(a === 255 ? nextRgb : `${nextRgb}${a.toString(16).padStart(2, "0")}`);
  };
  return (
    <span className="flex items-center gap-2">
      <input id={id} type="color" className="h-8 w-10 cursor-pointer rounded border-0 bg-transparent p-0"
        value={rgb} onChange={(e) => set(e.target.value, opacity)} />
      <input type="number" min={0} max={100} className="w-16 py-1 text-xs" value={opacity} title={t("chart.indicators.opacity")}
        onChange={(e) => set(rgb, Math.min(100, Math.max(0, Number(e.target.value) || 0)))} />
      <span className="text-xs text-zinc-500">%</span>
    </span>
  );
}

function ParamInput({ def, param, value, onChange, intervals, idPrefix }) {
  const id = `${idPrefix}-${param.name}`;
  if (param.type === "bool") {
    return (
      <label htmlFor={id} className="flex items-center gap-2 text-sm text-zinc-300">
        <input id={id} type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
        {paramLabel(def, param)}
      </label>
    );
  }
  let input;
  if (param.type === "source") {
    input = (
      <select id={id} className="w-full" value={value} onChange={(e) => onChange(e.target.value)}>
        {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
    );
  } else if (param.type === "color") {
    input = <ColorInput id={id} value={value} onChange={onChange} />;
  } else if (param.type === "timeframe") {
    input = (
      <select id={id} className="w-full" value={value} onChange={(e) => onChange(e.target.value)}>
        {intervalOptions(intervals, value).map((i) => <option key={i} value={i}>{intervalLabel(i)}</option>)}
      </select>
    );
  } else {
    input = (
      <input id={id} type="number" className="w-full" value={value} required
        step={param.type === "int" ? 1 : "any"} min={param.min ?? undefined} max={param.max ?? undefined}
        onChange={(e) => onChange(e.target.value)} />
    );
  }
  return (
    <label htmlFor={id} className="block space-y-1">
      <span className="label" title={param.label || undefined}>{paramLabel(def, param)}</span>
      {input}
    </label>
  );
}

/**
 * Settings of an indicator, built from its definition: numbers, source, on/off, colors and timeframes,
 * grouped like the original Pine inputs (one collapsible section per group).
 */
export default function ParamFields({ def, params, onChange, idPrefix = "ind" }) {
  const [intervals] = useChartIntervals();
  const groups = [];
  for (const param of def.params) {
    const group = groups.find((g) => g.name === param.group);
    if (group) group.params.push(param);
    else groups.push({ name: param.group, params: [param] });
  }
  const field = (p) => (
    <div key={p.name} className={p.type === "bool" ? "sm:col-span-2" : ""}>
      <ParamInput def={def} param={p} value={params[p.name] ?? p.default} intervals={intervals} idPrefix={idPrefix}
        onChange={(value) => onChange({ ...params, [p.name]: value })} />
    </div>
  );

  if (groups.length === 1 && !groups[0].name) {
    return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{def.params.map(field)}</div>;
  }
  return (
    <div className="space-y-2">
      {groups.map((group, i) => (
        <details key={group.name || i} open={i === 0} className="rounded-lg border border-white/[0.06] px-3 py-2">
          <summary className="cursor-pointer select-none text-xs font-semibold uppercase tracking-wider text-zinc-400">
            {groupLabel(group.name)} <span className="font-normal text-zinc-600">({group.params.length})</span>
          </summary>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">{group.params.map(field)}</div>
        </details>
      ))}
    </div>
  );
}
