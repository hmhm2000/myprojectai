import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { favoritesApi } from "../api/endpoints";
import CoinPicker from "../components/CoinPicker";
import ConfirmDialog from "../components/ConfirmDialog";
import NameDialog from "../components/NameDialog";
import PriceStatusBar from "../components/PriceStatusBar";
import { CloseIcon, EditIcon, PlusIcon, TrashIcon } from "../components/icons";
import { Change24h, CoinBadge, EmptyState, ErrorBanner } from "../components/ui";
import { usePrices } from "../context/contexts";
import { t } from "../i18n";
import Trans from "../i18n/Trans";
import { fmtUnitPrice } from "../lib/format";
import { sourceName } from "../lib/sources";

const SELECTED_KEY = "favorites:selected";

function FavoriteTile({ symbol, quote, onRemove }) {
  return (
    <div className="tile glow group p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-3">
          <CoinBadge symbol={symbol} />
          <div>
            <div className="font-semibold text-zinc-50">{symbol}</div>
            {quote && <span className="chip mt-0.5">{sourceName(quote.source)}</span>}
          </div>
        </div>
        <button
          type="button"
          className="btn-icon h-7 w-7 opacity-60 transition group-hover:opacity-100 hover:text-loss"
          title={t("favorites.removeCoin", { symbol })}
          onClick={onRemove}
        >
          <CloseIcon size={14} />
        </button>
      </div>
      <div className="mt-4 flex items-end justify-between gap-2">
        {quote ? (
          <>
            <span className={`num text-xl font-semibold ${quote.stale ? "text-zinc-400" : "text-zinc-50"}`}>
              {fmtUnitPrice(quote.price)}
            </span>
            <span className="text-right">
              <Change24h value={quote.change_24h_pct} />
              <div className="text-[10px] uppercase tracking-wider text-zinc-600">{t("prices.change24h")}</div>
            </span>
          </>
        ) : (
          <span className="text-sm text-amber-300">{t("coins.noPriceOnExchanges")}</span>
        )}
      </div>
    </div>
  );
}

export default function FavoritesPage() {
  const { prices } = usePrices();
  const [lists, setLists] = useState(null);
  const [selectedId, setSelectedId] = useState(() => Number(localStorage.getItem(SELECTED_KEY)) || null);
  const [newSymbol, setNewSymbol] = useState("");
  const [pickerKey, setPickerKey] = useState(0);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);
  const closeModal = useCallback(() => setModal(null), []);

  const load = useCallback(async () => {
    try {
      const data = await favoritesApi.list();
      setLists(data);
      setSelectedId((current) => (data.some((l) => l.id === current) ? current : data[0]?.id ?? null));
    } catch (err) {
      setError(errorMessage(err, "favorites.loadFailed"));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (selectedId) localStorage.setItem(SELECTED_KEY, String(selectedId));
  }, [selectedId]);

  const replaceList = (updated) => setLists((current) => current.map((l) => (l.id === updated.id ? updated : l)));
  const selected = lists?.find((l) => l.id === selectedId) ?? null;

  const addCoin = async (symbol) => {
    if (!symbol || !selected) return;
    try {
      replaceList(await favoritesApi.addCoin(selected.id, symbol));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    }
    setNewSymbol("");
    setPickerKey((k) => k + 1); // clears the search field
  };

  const removeCoin = async (symbol) => {
    try {
      replaceList(await favoritesApi.removeCoin(selected.id, symbol));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  if (lists === null) {
    return error ? <ErrorBanner>{error}</ErrorBanner> : <p className="text-sm text-zinc-500">{t("favorites.loading")}</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0">
          {lists.map((l) => (
            <button
              key={l.id}
              type="button"
              onClick={() => setSelectedId(l.id)}
              className={`shrink-0 rounded-xl border px-3.5 py-2 text-sm transition ${
                l.id === selectedId
                  ? "border-neon-green/40 bg-neon-green/10 text-zinc-50 shadow-neon-green"
                  : "border-white/[0.06] bg-ink-900 text-zinc-300 hover:border-white/15"
              }`}
            >
              {l.name} <span className="text-xs text-zinc-500">({l.coins.length})</span>
            </button>
          ))}
          <button type="button" className="btn-ghost shrink-0" onClick={() => setModal({ type: "create" })}>
            <PlusIcon size={16} /> {t("favorites.newList")}
          </button>
        </div>
        {selected && (
          <div className="flex shrink-0 gap-1">
            <button type="button" className="btn-icon" title={t("favorites.renameList")} onClick={() => setModal({ type: "rename" })}>
              <EditIcon size={16} />
            </button>
            <button type="button" className="btn-icon hover:text-loss" title={t("favorites.deleteList")} onClick={() => setModal({ type: "delete" })}>
              <TrashIcon size={16} />
            </button>
          </div>
        )}
      </div>

      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      {lists.length === 0 ? (
        <EmptyState
          title={t("favorites.emptyTitle")}
          action={
            <button type="button" className="btn-primary" onClick={() => setModal({ type: "create" })}>
              <PlusIcon size={16} /> {t("favorites.createList")}
            </button>
          }
        >
          {t("favorites.emptyText")}
        </EmptyState>
      ) : (
        selected && (
          <>
            <div className="tile space-y-3 px-4 py-3">
              <div className="flex flex-col gap-2 sm:flex-row">
                <div className="flex-1">
                  <CoinPicker
                    key={pickerKey}
                    value={newSymbol}
                    onChange={(symbol) => {
                      setNewSymbol(symbol);
                      if (symbol) addCoin(symbol);
                    }}
                    exclude={selected.coins.map((c) => c.symbol)}
                  />
                </div>
              </div>
              <PriceStatusBar compact />
            </div>

            {selected.coins.length === 0 ? (
              <EmptyState title={t("favorites.listEmptyTitle")}>{t("favorites.listEmptyText")}</EmptyState>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {selected.coins.map((coin) => (
                  <FavoriteTile key={coin.symbol} symbol={coin.symbol} quote={prices[coin.symbol]} onRemove={() => removeCoin(coin.symbol)} />
                ))}
              </div>
            )}
          </>
        )
      )}

      {modal?.type === "create" && (
        <NameDialog
          title={t("favorites.dialogs.createTitle")}
          submitLabel={t("common.actions.create")}
          onClose={closeModal}
          onSubmit={async (name) => {
            const created = await favoritesApi.create(name);
            setLists((current) => [...current, created]);
            setSelectedId(created.id);
          }}
        />
      )}
      {modal?.type === "rename" && selected && (
        <NameDialog
          title={t("favorites.dialogs.renameTitle")}
          initial={selected.name}
          onClose={closeModal}
          onSubmit={async (name) => replaceList(await favoritesApi.rename(selected.id, name))}
        />
      )}
      {modal?.type === "delete" && selected && (
        <ConfirmDialog
          title={t("favorites.dialogs.deleteTitle")}
          confirmLabel={t("favorites.dialogs.deleteConfirm")}
          onClose={closeModal}
          message={
            <p>
              <Trans
                k="favorites.dialogs.deleteMessage"
                values={{ name: <strong className="text-zinc-100">{selected.name}</strong>, count: selected.coins.length }}
              />
            </p>
          }
          onConfirm={async () => {
            await favoritesApi.remove(selected.id);
            await load();
          }}
        />
      )}
    </div>
  );
}
