import { useMemo, useState } from "react";
import { usePrices } from "../context/contexts";
import { t } from "../i18n";
import { useMyCoins } from "../lib/useMyCoins";
import { fmtUnitPrice } from "../lib/format";
import { sourceName } from "../lib/sources";
import { SearchIcon } from "./icons";
import { Change24h, CoinBadge } from "./ui";

const POPULAR = ["BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "SUI", "SPX", "PEPE", "LINK", "AVAX", "TON", "TRX"];
const LIMIT = 40;
const NONE = [];

/** Own coins (held, then favorites) first, then popular ones, then the rest - so the user's coins
 * are one click away and look-alike tickers of the long catalog come later. */
function rank(symbols, query, mine) {
  const own = mine.filter((s) => !query || s.includes(query));
  const ownSet = new Set(own);
  if (!query) {
    const popular = POPULAR.filter((s) => symbols.includes(s) && !ownSet.has(s));
    const rest = symbols.filter((s) => !POPULAR.includes(s) && !ownSet.has(s)).sort();
    return [...own, ...popular, ...rest].slice(0, LIMIT);
  }
  const byFit = (a, b) => Number(!a.startsWith(query)) - Number(!b.startsWith(query)) || a.length - b.length || a.localeCompare(b);
  const starts = [];
  const contains = [];
  for (const s of symbols) {
    if (s === query || ownSet.has(s)) continue;
    if (s.startsWith(query)) starts.push(s);
    else if (s.includes(query)) contains.push(s);
  }
  const exact = symbols.includes(query) && !ownSet.has(query) ? [query] : [];
  return [...own.sort(byFit), ...exact, ...starts.sort(byFit), ...contains.sort()].slice(0, LIMIT);
}

/**
 * Coin search over the price catalog (OKX + Bybit, same cache).
 * Also allows a symbol outside the catalog (then without a current price).
 */
export default function CoinPicker({ value, onChange, disabled = false, autoFocus = false, exclude = NONE, id }) {
  const { prices } = usePrices();
  const myCoins = useMyCoins();
  const [query, setQuery] = useState(value || "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const symbols = useMemo(() => Object.keys(prices).filter((s) => !exclude.includes(s)), [prices, exclude]);
  const q = query.trim().toUpperCase();
  const mine = useMemo(
    () => [...new Set([...myCoins.held, ...myCoins.favorites])].filter((s) => !exclude.includes(s)),
    [myCoins, exclude],
  );
  const held = useMemo(() => new Set(myCoins.held), [myCoins]);
  const favorite = useMemo(() => new Set(myCoins.favorites), [myCoins]);
  const matches = useMemo(() => rank(symbols, q, mine), [symbols, q, mine]);
  const canUseCustom = q && /^[A-Z0-9]{1,20}$/.test(q) && !prices[q] && !exclude.includes(q);
  const options = canUseCustom ? [...matches, { custom: q }] : matches;

  const select = (symbol) => {
    setQuery(symbol);
    setOpen(false);
    onChange(symbol);
  };

  const onKeyDown = (e) => {
    if (!open && (e.key === "ArrowDown" || e.key === "Enter")) {
      setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const option = options[active];
      if (option) select(typeof option === "string" ? option : option.custom);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative">
      <div className="relative">
        <SearchIcon size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
        <input
          id={id}
          type="text"
          className="w-full pl-9 uppercase placeholder:normal-case"
          placeholder={t("coins.picker.placeholder")}
          value={query}
          disabled={disabled}
          autoFocus={autoFocus}
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
            if (value) onChange("");
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded={open}
        />
      </div>

      {open && !disabled && options.length > 0 && (
        <ul
          className="absolute z-20 mt-1 max-h-64 w-full overflow-y-auto rounded-xl border border-white/10 bg-ink-800 p-1 shadow-2xl shadow-black/60"
          role="listbox"
        >
          {options.map((option, index) => {
            const isCustom = typeof option !== "string";
            const symbol = isCustom ? option.custom : option;
            const quote = prices[symbol];
            return (
              <li key={isCustom ? `custom-${symbol}` : symbol} role="option" aria-selected={index === active}>
                <button
                  type="button"
                  className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition ${
                    index === active ? "bg-white/[0.08]" : "hover:bg-white/[0.05]"
                  }`}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => select(symbol)}
                >
                  <CoinBadge symbol={symbol} size="sm" />
                  {isCustom ? (
                    <span className="text-zinc-300">
                      {t("coins.picker.useCustom", { symbol })}{" "}
                      <span className="text-xs text-amber-300">{t("coins.picker.noPriceOnExchanges")}</span>
                    </span>
                  ) : (
                    <>
                      <span className="flex flex-1 items-center gap-1.5 font-medium text-zinc-100">
                        {symbol}
                        {held.has(symbol) && <span className="chip text-[10px] text-neon-green">{t("coins.picker.held")}</span>}
                        {favorite.has(symbol) && <span className="text-[11px] text-amber-300" title={t("coins.picker.favorite")}>★</span>}
                      </span>
                      <span className="num text-zinc-300">{fmtUnitPrice(quote.price)}</span>
                      <span className="w-16 text-right">
                        <Change24h value={quote.change_24h_pct} />
                      </span>
                      <span className="chip w-14 justify-center">{sourceName(quote.source)}</span>
                    </>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
