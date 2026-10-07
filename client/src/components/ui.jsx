import { t } from "../i18n";
import { fmtMoney, fmtPct, pnlTone } from "../lib/format";

export function Field({ label, htmlFor, hint, children, className = "" }) {
  return (
    <div className={className}>
      {label && (
        <label className="label" htmlFor={htmlFor}>
          {label}
        </label>
      )}
      {children}
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}

/** Decimal number field kept as text (accepts a comma), without precision loss. */
export function DecimalInput({ value, onChange, className = "", ...props }) {
  return (
    <input
      type="text"
      inputMode="decimal"
      autoComplete="off"
      className={`num w-full ${className}`}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      {...props}
    />
  );
}

const HUES = [265, 150, 200, 320, 35, 180, 0, 95];

export function CoinBadge({ symbol, size = "md" }) {
  const hue = HUES[[...symbol].reduce((acc, ch) => acc + ch.charCodeAt(0), 0) % HUES.length];
  const dims = size === "sm" ? "h-7 w-7 text-[10px]" : "h-10 w-10 text-xs";
  return (
    <div
      className={`grid shrink-0 place-items-center rounded-full font-bold text-white ring-1 ring-white/10 ${dims}`}
      style={{
        background: `radial-gradient(circle at 30% 25%, hsl(${hue} 85% 62%), hsl(${hue} 70% 28%))`,
        boxShadow: `0 0 18px -6px hsl(${hue} 90% 60%)`,
      }}
    >
      {symbol.slice(0, 4)}
    </div>
  );
}

/** Profit/loss: amount + percent, green/red. */
export function Pnl({ value, pct, className = "", stacked = false }) {
  const tone = pnlTone(value ?? pct);
  if (value === null || value === undefined) {
    return <span className={`num text-zinc-500 ${className}`}>—</span>;
  }
  return (
    <span className={`num ${tone} ${stacked ? "flex flex-col items-end leading-tight" : ""} ${className}`}>
      <span>{fmtMoney(value, { signed: true })}</span>
      {pct !== undefined && pct !== null && (
        <span className={stacked ? "text-xs opacity-80" : "ml-1.5 text-xs opacity-80"}>({fmtPct(pct)})</span>
      )}
    </span>
  );
}

export function Change24h({ value }) {
  if (value === null || value === undefined) return <span className="text-xs text-zinc-600">—</span>;
  return <span className={`num text-xs ${pnlTone(value)}`}>{fmtPct(value)}</span>;
}

export function EmptyState({ title, children, action }) {
  return (
    <div className="tile flex flex-col items-center gap-3 px-6 py-12 text-center">
      <p className="text-base font-medium text-zinc-200">{title}</p>
      {children && <div className="max-w-md text-sm text-zinc-500">{children}</div>}
      {action}
    </div>
  );
}

export function ErrorBanner({ children, onClose }) {
  if (!children) return null;
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-loss/30 bg-loss/[0.08] px-3 py-2 text-sm text-red-200">
      <span>{children}</span>
      {onClose && (
        <button type="button" className="text-xs text-red-300 hover:text-red-100" onClick={onClose}>
          {t("common.actions.dismiss")}
        </button>
      )}
    </div>
  );
}
