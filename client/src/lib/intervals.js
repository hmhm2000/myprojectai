import { t } from "../i18n";

// Candle intervals: <n><unit>, unit m (minutes), h (hours), d (days), w (weeks), M (months).
// Same rules as the backend (server/services/intervals.py); custom ones (3d, 2w, ...) are aggregated there.
export const PRESET_INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"];

const UNIT_SECONDS = { m: 60, h: 3600, d: 86400, w: 604800, M: 2629800 };
const MAX_SECONDS = 366 * 86400;
const LEGACY_CUSTOM_KEY = "chart:customIntervals"; // old browser-only list, moved to the server once

/** "3D" -> "3d", "2W" -> "2w", "1M" -> "1M" (month), "15m" -> "15m"; null when invalid. */
export function parseInterval(input) {
  const match = String(input ?? "").trim().match(/^(\d{1,4})([mhdwMHDW])$/);
  if (!match) return null;
  const n = Number(match[1]);
  const unit = match[2] === "m" || match[2] === "M" ? match[2] : match[2].toLowerCase();
  if (n < 1 || (unit === "M" ? n > 12 : n * UNIT_SECONDS[unit] > MAX_SECONDS)) return null;
  return `${n}${unit}`;
}

/** Display label, e.g. "4H", "3D", "1M" (unit letters from chart.units in the locale files). */
export function intervalLabel(name) {
  const match = String(name ?? "").match(/^(\d+)([mhdwM])$/);
  return match ? `${match[1]}${t(`chart.units.${match[2]}`)}` : String(name ?? "");
}

/** Interval names for selects: the user's list (presets + custom, from the server) plus `current`. */
export function intervalOptions(intervals, current) {
  const list = intervals?.length ? intervals.map((i) => i.name) : PRESET_INTERVALS;
  return current && !list.includes(current) ? [...list, current] : list;
}

/** Custom intervals saved by the old browser-only version; removed from the browser when read. */
export function takeLegacyCustomIntervals() {
  try {
    const list = JSON.parse(localStorage.getItem(LEGACY_CUSTOM_KEY)) ?? [];
    localStorage.removeItem(LEGACY_CUSTOM_KEY);
    return list.filter((i) => parseInterval(i));
  } catch {
    return [];
  }
}
