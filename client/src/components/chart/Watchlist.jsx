import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import { favoritesApi } from "../../api/endpoints";
import { usePrices } from "../../context/contexts";
import { t } from "../../i18n";
import { fmtUnitPrice } from "../../lib/format";
import { Change24h, ErrorBanner } from "../ui";
import { CloseIcon, PlusIcon } from "../icons";

const SELECTED_KEY = "chart:watchlist";

function readSelected() {
  try {
    return Number(localStorage.getItem(SELECTED_KEY)) || null;
  } catch {
    return null;
  }
}

/**
 * Coin list next to the chart (like TradingView's watchlist) - the lists are the Favorites lists,
 * so coins added here appear in "Ulubione" and the other way round. Clicking a coin shows its chart.
 */
export default function Watchlist({ symbol, onSelect }) {
  const { prices } = usePrices();
  const [lists, setLists] = useState(null);
  const [selectedId, setSelectedId] = useState(readSelected);
  const [newName, setNewName] = useState(null);     // null = form closed
  const [error, setError] = useState(null);

  const load = useCallback(() => favoritesApi.list().then(setLists).catch((err) => setError(errorMessage(err))), []);
  useEffect(() => {
    load();
  }, [load]);

  const list = lists?.find((l) => l.id === selectedId) ?? lists?.[0] ?? null;
  useEffect(() => {
    if (list) {
      try {
        localStorage.setItem(SELECTED_KEY, String(list.id));
      } catch {
        // not remembered - fine
      }
    }
  }, [list]);

  const run = async (fn) => {
    setError(null);
    try {
      const changed = await fn();
      setLists((all) => all.map((l) => (l.id === changed.id ? changed : l)));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const create = async (e) => {
    e.preventDefault();
    if (!newName?.trim()) return;
    try {
      const created = await favoritesApi.create(newName.trim());
      setLists((all) => [...(all ?? []), created]);
      setSelectedId(created.id);
      setNewName(null);
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const inList = list?.coins.some((c) => c.symbol === symbol);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">{t("chart.watchlist.title")}</h2>
        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => setNewName(newName === null ? "" : null)}>
          <PlusIcon size={12} /> {t("chart.watchlist.newList")}
        </button>
      </div>
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      {newName !== null && (
        <form onSubmit={create} className="flex gap-1">
          <input autoFocus className="min-w-0 flex-1 py-1 text-sm" maxLength={60} value={newName}
            placeholder={t("chart.watchlist.listName")} onChange={(e) => setNewName(e.target.value)} />
          <button type="submit" className="btn-primary px-2 py-1 text-xs">{t("common.actions.create")}</button>
        </form>
      )}

      {lists !== null && lists.length === 0 && newName === null && (
        <p className="text-xs text-zinc-500">{t("chart.watchlist.noLists")}</p>
      )}

      {list && (
        <>
          <div className="flex items-center gap-2">
            <select className="min-w-0 flex-1 py-1 text-sm" value={list.id} onChange={(e) => setSelectedId(Number(e.target.value))}>
              {lists.map((l) => <option key={l.id} value={l.id}>{l.name} ({l.coins.length})</option>)}
            </select>
            <button type="button" className="btn-ghost shrink-0 px-2 py-1 text-xs" disabled={inList}
              title={inList ? t("chart.watchlist.alreadyIn", { symbol }) : undefined}
              onClick={() => run(() => favoritesApi.addCoin(list.id, symbol))}>
              <PlusIcon size={12} /> {symbol}
            </button>
          </div>
          {list.coins.length === 0 && <p className="text-xs text-zinc-500">{t("chart.watchlist.empty", { symbol })}</p>}
          <ul className="divide-y divide-white/[0.04]">
            {list.coins.map((coin) => {
              const quote = prices[coin.symbol];
              const active = coin.symbol === symbol;
              return (
                <li key={coin.symbol} className="group flex items-center">
                  <button type="button" onClick={() => onSelect(coin.symbol)}
                    className={`flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition ${
                      active ? "bg-neon-violet/15 text-zinc-50" : "text-zinc-200 hover:bg-white/[0.04]"}`}>
                    <span className="w-16 shrink-0 font-semibold">{coin.symbol}</span>
                    <span className="num flex-1 truncate text-right">{quote ? fmtUnitPrice(quote.price) : "—"}</span>
                    <span className="w-16 shrink-0 text-right text-xs">{quote ? <Change24h value={quote.change_24h_pct} /> : null}</span>
                  </button>
                  <button type="button" title={t("chart.watchlist.remove", { symbol: coin.symbol })}
                    className="btn-icon h-6 w-6 shrink-0 opacity-0 transition group-hover:opacity-100 hover:text-loss"
                    onClick={() => run(() => favoritesApi.removeCoin(list.id, coin.symbol))}>
                    <CloseIcon size={12} />
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}
