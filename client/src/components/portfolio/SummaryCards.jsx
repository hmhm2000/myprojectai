import { fmtMoney, fmtPct, pnlTone, toNumber } from "../../lib/format";
import { AlertIcon } from "../icons";

function Card({ label, children, sub, glow = "" }) {
  return (
    <div className={`tile glow ${glow} p-4 sm:p-5`}>
      <div className="text-xs font-medium uppercase tracking-wider text-zinc-500">{label}</div>
      <div className="num mt-2 text-xl font-semibold text-zinc-50 sm:text-2xl">{children}</div>
      {sub && <div className="mt-1 text-xs">{sub}</div>}
    </div>
  );
}

/** Podsumowanie całego portfela: wartość, zainwestowane, zysk/strata. */
export default function SummaryCards({ summary }) {
  const glowFor = (value) => {
    const n = toNumber(value);
    return n === null || n === 0 ? "" : n > 0 ? "glow-green" : "glow-red";
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card label="Wartość" glow="glow-violet">{fmtMoney(summary.value)}</Card>
        <Card label="Zainwestowane" sub={<span className="muted">koszt otwartych pozycji</span>}>
          {fmtMoney(summary.invested)}
        </Card>
        <Card
          label="Zysk otwartych pozycji"
          glow={glowFor(summary.unrealized_pnl)}
          sub={<span className={`num ${pnlTone(summary.unrealized_pnl_pct)}`}>{fmtPct(summary.unrealized_pnl_pct)}</span>}
        >
          <span className={pnlTone(summary.unrealized_pnl)}>{fmtMoney(summary.unrealized_pnl, { signed: true })}</span>
        </Card>
        <Card
          label="Zysk ogólny"
          glow={glowFor(summary.total_pnl)}
          sub={
            <span className="muted">
              <span className={`num ${pnlTone(summary.total_pnl_pct)}`}>{fmtPct(summary.total_pnl_pct)}</span>
              {" · "}w tym zrealizowany:{" "}
              <span className={`num ${pnlTone(summary.realized_pnl)}`}>{fmtMoney(summary.realized_pnl, { signed: true })}</span>
            </span>
          }
        >
          <span className={pnlTone(summary.total_pnl)}>{fmtMoney(summary.total_pnl, { signed: true })}</span>
        </Card>
      </div>

      {summary.missing_prices.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-xs text-amber-200">
          <AlertIcon size={16} className="shrink-0 text-amber-400" />
          Brak aktualnej ceny dla: {summary.missing_prices.join(", ")}. Te coiny nie są wliczone do wartości i zysku.
        </div>
      )}
    </div>
  );
}
