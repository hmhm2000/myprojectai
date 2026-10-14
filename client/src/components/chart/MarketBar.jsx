import { useEffect, useState } from "react";
import { marketApi } from "../../api/endpoints";
import { t } from "../../i18n";
import { fmtPct, pnlTone } from "../../lib/format";

const REFRESH_MS = 5 * 60_000;
const pct = (value) => (value === null || value === undefined ? "—" : fmtPct(value, { signed: false }));

/** BTC / ETH / USDT dominance and the total market cap (CoinGecko, current values). */
export default function MarketBar() {
  const [data, setData] = useState(null);

  useEffect(() => {
    const load = () => marketApi.global().then(setData).catch(() => {});
    load();
    const id = setInterval(() => document.visibilityState === "visible" && load(), REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  if (!data) return null;
  const cap = data.total_market_cap_usd;
  const items = [
    ["BTC.D", pct(data.btc_dominance)],
    ["ETH.D", pct(data.eth_dominance)],
    ["USDT.D", pct(data.usdt_dominance)],
    ["USDC.D", pct(data.usdc_dominance)],
  ];
  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-1 text-xs ${data.stale ? "opacity-60" : ""}`}
      title={t("chart.market.title", { source: data.source })}>
      {items.map(([label, value]) => (
        <span key={label} className="num text-zinc-400">
          {label} <span className="text-zinc-100">{value}</span>
        </span>
      ))}
      {cap && (
        <span className="num text-zinc-400">
          {t("chart.market.cap")}{" "}
          <span className="text-zinc-100">{t("chart.market.trillions", { value: (cap / 1e12).toLocaleString("pl-PL", { maximumFractionDigits: 2 }) })}</span>
          {data.market_cap_change_24h_pct !== null && (
            <span className={`ml-1 ${pnlTone(data.market_cap_change_24h_pct)}`}>{fmtPct(data.market_cap_change_24h_pct)}</span>
          )}
        </span>
      )}
    </div>
  );
}
