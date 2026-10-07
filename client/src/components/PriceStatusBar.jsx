import { useEffect, useState } from "react";
import { usePrices } from "../context/contexts";
import { t } from "../i18n";
import Trans from "../i18n/Trans";
import { fmtDateTime, fmtTime } from "../lib/format";
import { sourceErrorText, sourceName } from "../lib/sources";
import { AlertIcon, RefreshIcon } from "./icons";

function useCountdown(until) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    setNow(Date.now());
    if (until <= Date.now()) return undefined;
    const id = setInterval(() => {
      setNow(Date.now());
      if (Date.now() >= until) clearInterval(id);
    }, 250);
    return () => clearInterval(id);
  }, [until]);
  return Math.max(0, Math.ceil((until - now) / 1000));
}

/** Price status + "Refresh prices" button (rate limited, also enforced by the backend). */
export default function PriceStatusBar({ compact = false }) {
  const { data, error, refreshing, cooldownUntil, forceRefresh } = usePrices();
  const wait = useCountdown(cooldownUntil);
  const failed = data?.sources.filter((s) => !s.ok || s.stale) ?? [];
  const stale = data?.stale;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-400">
          <span className={`inline-block h-2 w-2 rounded-full ${stale ? "bg-amber-400" : "bg-neon-green shadow-neon-green"}`} />
          {data?.fetched_at ? (
            <span>
              <Trans k="prices.statusBar.pricesFrom" values={{ time: <span className="num text-zinc-300">{fmtTime(data.fetched_at)}</span> }} />
              {!compact && (
                <span className="muted"> · {data.sources.map((s) => sourceName(s.name)).join(" + ")} · {data.quote_currency}</span>
              )}
            </span>
          ) : (
            <span>{data ? t("prices.statusBar.noPrices") : t("prices.statusBar.loading")}</span>
          )}
        </div>
        <button
          type="button"
          className="btn-ghost py-1.5 text-xs"
          onClick={forceRefresh}
          disabled={refreshing || wait > 0}
          title={t("prices.statusBar.refreshTitle")}
        >
          <RefreshIcon size={14} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? t("prices.statusBar.refreshing") : wait > 0 ? t("prices.statusBar.refreshWait", { seconds: wait }) : t("prices.statusBar.refresh")}
        </button>
      </div>

      {(stale && failed.length > 0) || error ? (
        <div className="flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-xs text-amber-200">
          <AlertIcon size={16} className="mt-px shrink-0 text-amber-400" />
          <div className="space-y-0.5">
            {error && <p>{error}</p>}
            {failed.map((s) => (
              <p key={s.name}>
                <span className="font-semibold">{sourceName(s.name)}:</span>{" "}
                {s.fetched_at
                  ? t("prices.statusBar.staleSince", { date: fmtDateTime(s.fetched_at) })
                  : t("prices.statusBar.noData")}
                {s.error_code && <span className="text-amber-300/70"> ({sourceErrorText(s.error_code)})</span>}
              </p>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
