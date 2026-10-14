import { t } from "../../i18n";
import ColorPicker from "../ColorPicker";
import { drawnOutputs, outputLabel, resolveColor } from "../../lib/indicatorMeta";

const LINE_STYLE_NAMES = ["solid", "dashed", "dotted", "large_dashed", "sparse_dotted"];
const WIDTH_PLOTS = new Set(["line", "stepline", "area", "points"]);
const LINE_STYLE_PLOTS = new Set(["line", "stepline", "area"]);
const FALLBACK = "#a1a1aa";

/** "#rrggbb" of a color spec ("#rrggbb[aa]" or "@param"), for the color picker. */
function hexOf(spec, params) {
  const rgba = resolveColor(spec, params);
  if (!rgba) return FALLBACK;
  const [r, g, b] = rgba.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);
  return `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/** Defaults of one output's style (what "no own style" looks like). */
function defaultsOf(output, params) {
  return {
    visible: true,
    color: hexOf(output.color, params),
    opacity: Math.round((output.opacity ?? 1) * 100),
    width: output.plot === "points" ? Math.max(1, Math.round((output.radius ?? 2) - 1)) : output.width ?? 1,
    line_style: "solid",
  };
}

/**
 * The Style section (like TradingView's Style tab): for every drawn line / band / histogram - visible,
 * color + opacity (one picker: quick colors, slider, eyedropper), thickness and line style. `styles` = { output: { only the changed fields } }.
 * A color that comes from an indicator color setting (Pine input.color) is changed there (`params`).
 */
/** Name of an output; a fill without its own name is named after the two lines it fills between. */
function labelOf(def, output) {
  const label = outputLabel(def, output);
  if (output.plot !== "band" || label !== output.name || output.between?.length !== 2) return label;
  const [a, b] = output.between.map((name) => outputLabel(def, def.outputs.find((o) => o.name === name) ?? { name }));
  return t("chart.style.fill", { a, b });
}

const BACK = new Set(["band", "background"]);   // fills / backgrounds after the lines

export default function StyleFields({ def, params, styles, onStyles, onParams }) {
  const outputs = [...drawnOutputs(def)].sort((a, b) => BACK.has(a.plot) - BACK.has(b.plot));
  if (!outputs.length) return null;

  // changes of one output: { field: value } (a value equal to the default = no own style for it)
  const set = (output, changes) => {
    const own = { ...(styles[output.name] ?? {}) };
    const base = defaultsOf(output, params);
    for (const [field, value] of Object.entries(changes)) {
      if (field === "color" && output.color?.startsWith("@")) {
        const name = output.color.slice(1);
        const alpha = String(params[name] ?? "").slice(7, 9);   // keep the setting's own transparency
        if (value !== base.color) onParams({ ...params, [name]: `${value}${alpha}` });
        continue;
      }
      if (value === base[field]) delete own[field];
      else own[field] = value;
    }
    const next = { ...styles };
    if (Object.keys(own).length) next[output.name] = own;
    else delete next[output.name];
    onStyles(next);
  };

  return (
    <details open className="rounded-lg border border-white/[0.06] px-3 py-2">
      <summary className="cursor-pointer select-none text-xs font-semibold uppercase tracking-wider text-zinc-400">
        {t("chart.style.title")} <span className="font-normal text-zinc-600">({outputs.length})</span>
      </summary>
      <div className="mt-3 space-y-2">
        {outputs.map((output) => {
          const base = defaultsOf(output, params);
          const own = styles[output.name] ?? {};
          const value = { ...base, ...own };
          const colorable = !output.palette?.length;
          const id = `style-${output.name}`;
          return (
            <div key={output.name} className="grid grid-cols-[minmax(0,1fr)_2.25rem_4.5rem_7.5rem] items-center gap-2">
              <label htmlFor={id} className="flex min-w-0 items-center gap-2 text-sm text-zinc-300">
                <input id={id} type="checkbox" checked={value.visible} onChange={(e) => set(output, { visible: e.target.checked })} />
                <span className={`truncate ${value.visible ? "" : "text-zinc-500"}`} title={labelOf(def, output)}>{labelOf(def, output)}</span>
              </label>
              <ColorPicker color={colorable ? value.color : null} opacity={value.opacity} title={t("chart.style.color")}
                onChange={(color, opacity) => set(output, colorable ? { color, opacity } : { opacity })} />
              {WIDTH_PLOTS.has(output.plot) ? (
                <select className="w-full px-1.5 py-1 text-xs" title={t("chart.style.width")} value={value.width}
                  onChange={(e) => set(output, { width: Number(e.target.value) })}>
                  {[1, 2, 3, 4].map((w) => <option key={w} value={w}>{w} px</option>)}
                </select>
              ) : <span />}
              {LINE_STYLE_PLOTS.has(output.plot) ? (
                <select className="w-full px-1.5 py-1 text-xs" title={t("chart.style.lineStyle")} value={value.line_style}
                  onChange={(e) => set(output, { line_style: e.target.value })}>
                  {LINE_STYLE_NAMES.map((st) => <option key={st} value={st}>{t(`chart.style.lineStyles.${st}`)}</option>)}
                </select>
              ) : <span />}
            </div>
          );
        })}
      </div>
    </details>
  );
}
