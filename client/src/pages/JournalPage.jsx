import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { journalApi, portfoliosApi } from "../api/endpoints";
import { ErrorBanner, Pnl } from "../components/ui";
import { t } from "../i18n";
import { fmtDate, fmtDuration, fmtPct, pnlTone } from "../lib/format";

const optDuration = (seconds) => (seconds === null || seconds === undefined ? "—" : fmtDuration(seconds));

function Summary({ stats }) {
  const o = stats.overall;
  const items = [
    [t("journal.summary.trades"), o.trades],
    [t("journal.summary.winRate"), fmtPct(o.win_rate, { signed: false })],
    [t("journal.summary.totalPnl"), <Pnl key="total" value={o.total_pnl} />],
    [t("journal.summary.avgPnl"), <Pnl key="avg" value={o.avg_pnl} pct={o.avg_pnl_pct} />],
    [t("journal.summary.avgDuration"), optDuration(o.avg_duration_seconds)],
    [t("journal.summary.avgBelow"), optDuration(o.avg_below_seconds)],
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
      {items.map(([label, value]) => (
        <div key={label} className="tile p-3">
          <div className="text-[11px] uppercase tracking-wider text-zinc-500">{label}</div>
          <div className="num mt-1 text-lg text-zinc-100">{value}</div>
        </div>
      ))}
    </div>
  );
}

function Compare({ stats }) {
  const rows = [
    ["count", (g) => g.trades],
    ["avgPnl", (g) => <Pnl value={g.avg_pnl} />],
    ["avgPnlPct", (g) => <span className={pnlTone(g.avg_pnl_pct)}>{fmtPct(g.avg_pnl_pct)}</span>],
    ["avgDuration", (g) => optDuration(g.avg_duration_seconds)],
    ["avgBelow", (g) => optDuration(g.avg_below_seconds)],
    ["avgBelowPct", (g) => fmtPct(g.avg_below_pct, { signed: false })],
  ];
  return (
    <Section title={t("journal.compare.title")}>
      <table className="w-full min-w-[26rem] text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <th className="pb-2" />
            <th className="pb-2 text-right">{t("journal.compare.winners")}</th>
            <th className="pb-2 text-right">{t("journal.compare.losers")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([key, render]) => (
            <tr key={key} className="border-t border-white/[0.04]">
              <td className="py-1.5 text-zinc-400">{t(`journal.compare.${key}`)}</td>
              <td className="num py-1.5 text-right">{render(stats.winners)}</td>
              <td className="num py-1.5 text-right">{render(stats.losers)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

/** Table of group stats - used for tags and keywords. */
function StatsTable({ title, hint, labelHeader, rows, label }) {
  if (!rows.length) return null;
  return (
    <Section title={title} hint={hint}>
      <table className="w-full min-w-[40rem] text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <th className="pb-2">{labelHeader}</th>
            <th className="pb-2 text-right">{t("journal.table.trades")}</th>
            <th className="pb-2 text-right">{t("journal.table.winRate")}</th>
            <th className="pb-2 text-right">{t("journal.table.avgPnl")}</th>
            <th className="pb-2 text-right">{t("journal.table.avgPnlPct")}</th>
            <th className="pb-2 text-right">{t("journal.table.totalPnl")}</th>
            <th className="pb-2 text-right">{t("journal.table.avgDuration")}</th>
            <th className="pb-2 text-right">{t("journal.table.avgBelowPct")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={label(row)} className="border-t border-white/[0.04]">
              <td className="py-1.5 text-zinc-200">{label(row)}</td>
              <td className="num py-1.5 text-right">{row.trades}</td>
              <td className="num py-1.5 text-right">{fmtPct(row.win_rate, { signed: false })}</td>
              <td className="py-1.5 text-right"><Pnl value={row.avg_pnl} /></td>
              <td className={`num py-1.5 text-right ${pnlTone(row.avg_pnl_pct)}`}>{fmtPct(row.avg_pnl_pct)}</td>
              <td className="py-1.5 text-right"><Pnl value={row.total_pnl} /></td>
              <td className="num py-1.5 text-right">{optDuration(row.avg_duration_seconds)}</td>
              <td className="num py-1.5 text-right">{fmtPct(row.avg_below_pct, { signed: false })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

function Trades({ trades }) {
  return (
    <Section title={t("journal.trades.title")}>
      <table className="w-full min-w-[48rem] text-sm">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-wider text-zinc-500">
            <th className="pb-2">{t("journal.trades.closed")}</th>
            <th className="pb-2">{t("journal.trades.symbol")}</th>
            <th className="pb-2 text-right">{t("journal.trades.pnl")}</th>
            <th className="pb-2 text-right">{t("journal.trades.duration")}</th>
            <th className="pb-2 text-right">{t("journal.trades.below")}</th>
            <th className="pb-2 pl-4">{t("journal.trades.reasons")}</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr key={trade.position_id} className="border-t border-white/[0.04] align-top">
              <td className="py-2 text-zinc-400">{fmtDate(trade.closed_at)}</td>
              <td className="py-2 font-medium text-zinc-100">{trade.symbol}</td>
              <td className="py-2 text-right"><Pnl value={trade.pnl} pct={trade.pnl_pct} stacked /></td>
              <td className="num py-2 text-right">{optDuration(trade.duration_seconds)}</td>
              <td className="num py-2 text-right">{fmtPct(trade.below_pct, { signed: false })}</td>
              <td className="py-2 pl-4 text-xs text-zinc-400">
                {trade.tags.length > 0 && (
                  <div className="mb-1 flex flex-wrap gap-1">
                    {trade.tags.map((tag) => <span key={tag} className="chip text-neon-violet">{tag}</span>)}
                  </div>
                )}
                {trade.entry_reason && <p className="whitespace-pre-line text-zinc-300">{trade.entry_reason}</p>}
                {trade.exit_reasons.length > 0 && (
                  <p className="mt-1"><span className="text-zinc-500">{t("journal.trades.exit")}</span> {trade.exit_reasons.join(" · ")}</p>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

function Section({ title, hint, children }) {
  return (
    <section className="tile p-4">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">{title}</h2>
      {hint && <p className="mt-0.5 text-xs text-zinc-500">{hint}</p>}
      <div className="mt-3 overflow-x-auto">{children}</div>
    </section>
  );
}

export default function JournalPage() {
  const [portfolios, setPortfolios] = useState([]);
  const [portfolioId, setPortfolioId] = useState("");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    portfoliosApi.list().then(setPortfolios).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    journalApi
      .stats(portfolioId || null)
      .then((data) => !cancelled && (setStats(data), setError(null)))
      .catch((err) => !cancelled && setError(errorMessage(err, "journal.loadFailed")))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [portfolioId]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">{t("journal.title")}</h1>
          {stats && <p className="text-xs text-zinc-500">{t("journal.intro", { count: stats.open_positions })}</p>}
        </div>
        <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)} className="text-sm">
          <option value="">{t("journal.allPortfolios")}</option>
          {portfolios.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>

      <ErrorBanner>{error}</ErrorBanner>
      {loading && <p className="text-sm text-zinc-500">{t("journal.loading")}</p>}

      {stats && !loading && (stats.overall.trades === 0 ? (
        <p className="text-sm text-zinc-500">{t("journal.empty")}</p>
      ) : (
        <>
          <Summary stats={stats} />
          <Compare stats={stats} />
          <StatsTable title={t("journal.tags.title")} labelHeader={t("journal.tags.tag")} rows={stats.tags}
            label={(row) => row.tag ?? t("journal.tags.untagged")} />
          <StatsTable title={t("journal.keywords.title")} hint={t("journal.keywords.hint")}
            labelHeader={t("journal.keywords.keyword")} rows={stats.keywords} label={(row) => row.keyword} />
          <Trades trades={stats.trades} />
        </>
      ))}
    </div>
  );
}

