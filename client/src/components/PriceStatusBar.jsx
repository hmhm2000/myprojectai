import { useEffect, useState } from "react";
import { usePrices } from "../context/contexts";
import { fmtDateTime, fmtTime } from "../lib/format";
import { AlertIcon, RefreshIcon } from "./icons";

const SOURCE_NAMES = { okx: "OKX", bybit: "Bybit" };

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

/** Stan cen + przycisk "Odśwież ceny" (z limitem, który pilnuje też backend). */
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
              Ceny z <span className="num text-zinc-300">{fmtTime(data.fetched_at)}</span>
              {!compact && (
                <span className="muted"> · {data.sources.map((s) => SOURCE_NAMES[s.name] ?? s.name).join(" + ")} · {data.quote_currency}</span>
              )}
            </span>
          ) : (
            <span>{data ? "Brak cen" : "Ładowanie cen…"}</span>
          )}
        </div>
        <button
          type="button"
          className="btn-ghost py-1.5 text-xs"
          onClick={forceRefresh}
          disabled={refreshing || wait > 0}
          title="Wymusza pobranie cen z giełd"
        >
          <RefreshIcon size={14} className={refreshing ? "animate-spin" : ""} />
          {refreshing ? "Odświeżanie…" : wait > 0 ? `Odśwież (${wait}s)` : "Odśwież ceny"}
        </button>
      </div>

      {(stale && failed.length > 0) || error ? (
        <div className="flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2 text-xs text-amber-200">
          <AlertIcon size={16} className="mt-px shrink-0 text-amber-400" />
          <div className="space-y-0.5">
            {error && <p>{error}</p>}
            {failed.map((s) => (
              <p key={s.name}>
                <span className="font-semibold">{SOURCE_NAMES[s.name] ?? s.name}:</span>{" "}
                {s.fetched_at
                  ? `ceny nieaktualne, ostatnie z ${fmtDateTime(s.fetched_at)}.`
                  : "brak danych."}
                {s.error && <span className="text-amber-300/70"> ({s.error})</span>}
              </p>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
