import { hasTranslation, t } from "../i18n";

// Labels, defaults and colors of indicator definitions (GET /api/indicators).

export const SOURCES = ["close", "open", "high", "low", "hl2", "hlc3", "ohlc4"];

export const defaultParams = (def) => Object.fromEntries(def.params.map((p) => [p.name, p.default]));

const translated = (keys, fallback) => {
  const key = keys.find((k) => hasTranslation(k));
  return key ? t(key) : fallback;
};

/** Parameter label: translation for this indicator, then the shared one, then the original (Pine) title. */
export const paramLabel = (def, param) =>
  translated([`chart.indicatorParams.${def.id}.${param.name}`, `chart.params.${param.name}`], param.label || param.name);

export const groupLabel = (group) => translated([`chart.paramGroups.${group}`], group);

export const outputLabel = (def, output) =>
  translated([`chart.indicatorOutputs.${def.id}.${output.name}`, `alerts.outputs.${output.name}`], output.label || output.name);

/** Outputs that can be used in alert conditions. */
export const alertOutputs = (def) => def.outputs.filter((o) => o.alert !== false && o.plot !== "band");

/** Tile text: "SMA 100", "BB 20, 2", "RSI 14 (hl2)"; indicators with many settings list only `def.summary`. */
export function summaryText(def, params) {
  const shown = def.summary?.length
    ? def.params.filter((p) => def.summary.includes(p.name))
    : def.params.filter((p) => p.type === "int" || p.type === "float");
  const values = shown.map((p) => params[p.name] ?? p.default);
  const sourceParam = def.params.find((p) => p.type === "source" && p.name === "source");
  const source = sourceParam && params.source && params.source !== sourceParam.default ? ` (${params.source})` : "";
  return `${def.name} ${values.join(", ")}${source}`.trim();
}

/** "#rrggbb" / "#rrggbbaa" / "@param" (+ opacity multiplier) -> CSS rgba(). */
export function resolveColor(spec, params, opacity = 1) {
  if (!spec) return null;
  const hex = spec.startsWith("@") ? params?.[spec.slice(1)] : spec;
  if (typeof hex !== "string" || !/^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(hex)) return null;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const alpha = (hex.length === 9 ? parseInt(hex.slice(7, 9), 16) / 255 : 1) * opacity;
  return `rgba(${r},${g},${b},${Math.round(alpha * 1000) / 1000})`;
}
