import { useSearchParams } from "react-router-dom";
import CoinPicker from "../components/CoinPicker";
import CandleChart from "../components/chart/CandleChart";
import { t } from "../i18n";

const INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"];

export default function ChartPage() {
  const [params, setParams] = useSearchParams();
  const symbol = (params.get("symbol") || "BTC").toUpperCase();
  const interval = INTERVALS.includes(params.get("interval")) ? params.get("interval") : "1h";
  const update = (changes) => setParams({ symbol, interval, ...changes }, { replace: true });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="w-56">
          <CoinPicker key={symbol} value={symbol} onChange={(s) => s && update({ symbol: s })} />
        </div>
        <div className="flex flex-wrap gap-1">
          {INTERVALS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => update({ interval: value })}
              className={`rounded-lg px-2.5 py-1.5 text-xs transition ${
                value === interval ? "bg-neon-violet/20 text-zinc-50" : "text-zinc-400 hover:bg-white/5"
              }`}
            >
              {t(`chart.intervals.${value}`)}
            </button>
          ))}
        </div>
      </div>
      <div className="tile p-2">
        <CandleChart symbol={symbol} interval={interval} />
      </div>
    </div>
  );
}
