// Backend liczy wszystko w Decimal i zwraca kwoty jako stringi.
// Tu tylko formatujemy je do wyświetlenia.

const LOCALE = "pl-PL";
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

/** Cena coina: liczba miejsc po przecinku zależy od wielkości (BTC vs memecoiny). */
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

/** Kwota w USDT (wartość, koszt, zysk). */
export function fmtMoney(value, { signed = false } = {}) {
  const n = toNumber(value);
  if (n === null) return DASH;
  const abs = Math.abs(n);
  const body = abs !== 0 && abs < 1 ? nf(2, 4).format(abs) : nf(2, 2).format(abs);
  const sign = n < 0 ? "−" : signed && n > 0 ? "+" : "";
  return `${sign}$${body}`;
}

/** Ilość coina: do 8 miejsc, bez zbędnych zer. */
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

/** Klasa koloru: zysk zielony, strata czerwona. */
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

// ------------------------------------------------------------------ formularze

/** "0,5" / " 1.25 " -> "0.5" / "1.25"; null gdy to nie jest poprawna liczba >= 0. */
export function parseAmount(input) {
  const text = String(input ?? "").trim().replace(/\s/g, "").replace(",", ".");
  if (!/^(\d+\.?\d*|\.\d+)$/.test(text)) return null;
  return text.startsWith(".") ? `0${text}` : text.replace(/\.$/, "");
}

/** Wartość do <input type="datetime-local"> w czasie lokalnym. */
export function toLocalInput(date = new Date()) {
  const d = new Date(date);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Iloczyn do podglądu w formularzu (tylko wyświetlanie; właściwe liczenie robi backend). */
export function previewMultiply(a, b) {
  const x = toNumber(parseAmount(a));
  const y = toNumber(parseAmount(b));
  return x === null || y === null ? null : x * y;
}
