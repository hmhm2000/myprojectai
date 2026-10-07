// The backend calculates everything in Decimal and returns amounts as strings.
// This module only formats them for display (locale and currency symbol come from i18n).
import { CURRENCY_SYMBOL, LOCALE_TAG as LOCALE, t } from "../i18n";

const formatters = new Map();

function nf(minimumFractionDigits, maximumFractionDigits) {
  const key = `${minimumFractionDigits}-${maximumFractionDigits}`;
  if (!formatters.has(key)) {
    formatters.set(key, new Intl.NumberFormat(LOCALE, { minimumFractionDigits, maximumFractionDigits }));
  }
  return formatters.get(key);
}

export function toNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

const DASH = "—";

/** Coin price: number of decimals depends on magnitude (BTC vs memecoins). */
export function fmtPrice(value) {
  const n = toNumber(value);
  if (n === null) return DASH;
  const abs = Math.abs(n);
  if (abs >= 1000) return nf(2, 2).format(n);
  if (abs >= 1) return nf(2, 4).format(n);
  if (abs >= 0.01) return nf(2, 6).format(n);
  if (abs === 0) return "0";
  return new Intl.NumberFormat(LOCALE, { maximumSignificantDigits: 4 }).format(n);
}

/** Coin price with the currency symbol, e.g. "$85 654,30". */
export function fmtUnitPrice(value) {
  return toNumber(value) === null ? DASH : `${CURRENCY_SYMBOL}${fmtPrice(value)}`;
}

/** Amount in the quote currency (value, cost, profit). */
export function fmtMoney(value, { signed = false } = {}) {
  const n = toNumber(value);
  if (n === null) return DASH;
  const abs = Math.abs(n);
  const body = abs !== 0 && abs < 1 ? nf(2, 4).format(abs) : nf(2, 2).format(abs);
  const sign = n < 0 ? "−" : signed && n > 0 ? "+" : "";
  return `${sign}${CURRENCY_SYMBOL}${body}`;
}

/** Coin quantity: up to 8 decimals, no trailing zeros. */
export function fmtQty(value) {
  const n = toNumber(value);
  if (n === null) return DASH;
  return nf(0, 8).format(n);
}

export function fmtPct(value, { signed = true } = {}) {
  const n = toNumber(value);
  if (n === null) return DASH;
  const sign = n < 0 ? "−" : signed && n > 0 ? "+" : "";
  return `${sign}${nf(2, 2).format(Math.abs(n))}%`;
}

/** Color class: profit green, loss red. */
export function pnlTone(value) {
  const n = toNumber(value);
  if (n === null || n === 0) return "text-zinc-300";
  return n > 0 ? "text-profit" : "text-loss";
}

export function fmtDate(value) {
  if (!value) return DASH;
  return new Date(value).toLocaleDateString(LOCALE, { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function fmtDateTime(value) {
  if (!value) return DASH;
  return new Date(value).toLocaleString(LOCALE, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtTime(value) {
  if (!value) return DASH;
  return new Date(value).toLocaleTimeString(LOCALE, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Duration like "3 d 4 h", "5 h 12 min", "12 min" (units from common.duration in the locale files). */
export function fmtDuration(seconds) {
  if (seconds === null || seconds === undefined) return DASH;
  const minutes = Math.floor(seconds / 60);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const mins = minutes % 60;
  if (days > 0) return [t("common.duration.days", { n: days }), hours && t("common.duration.hours", { n: hours })].filter(Boolean).join(" ");
  if (hours > 0) return [t("common.duration.hours", { n: hours }), mins && t("common.duration.minutes", { n: mins })].filter(Boolean).join(" ");
  return t("common.duration.minutes", { n: mins });
}

/** Lifetime of a position in seconds: purchase -> last sale (closed) or now (open). Dates are local. */
export function positionDurationSeconds(position, now = new Date()) {
  const end = position.is_closed && position.sales.length
    ? Math.max(...position.sales.map((s) => new Date(s.sold_at).getTime()))
    : now.getTime();
  return Math.max(0, Math.round((end - new Date(position.bought_at).getTime()) / 1000));
}

// ------------------------------------------------------------------ forms

/** "0,5" / " 1.25 " -> "0.5" / "1.25"; null when it is not a valid number >= 0. */
export function parseAmount(input) {
  const text = String(input ?? "").trim().replace(/\s/g, "").replace(",", ".");
  if (!/^(\d+\.?\d*|\.\d+)$/.test(text)) return null;
  return text.startsWith(".") ? `0${text}` : text.replace(/\.$/, "");
}

/** Value for <input type="datetime-local"> in local time. */
export function toLocalInput(date = new Date()) {
  const d = new Date(date);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Product for form previews (display only; the backend does the real calculation). */
export function previewMultiply(a, b) {
  const x = toNumber(parseAmount(a));
  const y = toNumber(parseAmount(b));
  return x === null || y === null ? null : x * y;
}
