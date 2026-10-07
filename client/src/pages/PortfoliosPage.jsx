import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { portfoliosApi } from "../api/endpoints";
import ConfirmDialog from "../components/ConfirmDialog";
import NameDialog from "../components/NameDialog";
import CoinRow from "../components/portfolio/CoinRow";
import SummaryCards from "../components/portfolio/SummaryCards";
import PositionForm from "../components/PositionForm";
import PriceStatusBar from "../components/PriceStatusBar";
import SaleForm from "../components/SaleForm";
import { EditIcon, EyeIcon, PlusIcon, TrashIcon } from "../components/icons";
import { EmptyState, ErrorBanner } from "../components/ui";
import { usePrices } from "../context/contexts";
import { fmtDate, fmtMoney, fmtPrice, fmtQty } from "../lib/format";

const SELECTED_KEY = "portfolio:selected";
const SHOW_CLOSED_KEY = "positions:showClosed";
const SORT_KEY = "positions:sort";

function readSelected() {
  const id = Number(localStorage.getItem(SELECTED_KEY));
  return Number.isFinite(id) && id > 0 ? id : null;
}

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

export default function PortfoliosPage() {
  const { version } = usePrices();
  const [portfolios, setPortfolios] = useState(null);
  const [selectedId, setSelectedId] = useState(readSelected);
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());
  const [modal, setModal] = useState(null);
  const closeModal = useCallback(() => setModal(null), []);
  // Zamknięte pozycje domyślnie ukryte; sortowanie zapamiętane osobno dla każdego coina.
  const [showClosed, setShowClosed] = useState(() => readJson(SHOW_CLOSED_KEY, false));
  const [sortModes, setSortModes] = useState(() => readJson(SORT_KEY, {}));

  useEffect(() => localStorage.setItem(SHOW_CLOSED_KEY, JSON.stringify(showClosed)), [showClosed]);
  useEffect(() => localStorage.setItem(SORT_KEY, JSON.stringify(sortModes)), [sortModes]);

  // ------------------------------------------------------------- ładowanie

  const loadList = useCallback(async () => {
    try {
      const list = await portfoliosApi.list();
      setPortfolios(list);
      setSelectedId((current) => (list.some((p) => p.id === current) ? current : list[0]?.id ?? null));
    } catch (err) {
      setError(errorMessage(err, "Nie udało się wczytać portfeli"));
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    if (selectedId) localStorage.setItem(SELECTED_KEY, String(selectedId));
  }, [selectedId]);

  // Widok portfela: przy zmianie portfela i gdy backend ma nowe ceny (bez odpytywania giełdy).
  useEffect(() => {
    if (!selectedId) {
      setView(null);
      return undefined;
    }
    let cancelled = false;
    portfoliosApi
      .get(selectedId)
      .then((data) => !cancelled && setView(data))
      .catch((err) => !cancelled && setError(errorMessage(err, "Nie udało się wczytać portfela")));
    return () => {
      cancelled = true;
    };
  }, [selectedId, version]);

  /** Każda zmiana zwraca przeliczony portfel - podmieniamy widok i podsumowanie na liście. */
  const applyView = useCallback((data) => {
    setView(data);
    setPortfolios((list) =>
      list?.map((p) =>
        p.id === data.id
          ? { ...p, name: data.name, summary: data.summary, positions_count: data.coins.reduce((n, c) => n + c.positions.length, 0) }
          : p,
      ),
    );
  }, []);

  const toggle = (symbol) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });

  // ------------------------------------------------------------- akcje

  const actions = {
    addPosition: (symbol = "") => setModal({ type: "position", symbol }),
    editPosition: (position) => setModal({ type: "position", position }),
    deletePosition: (coin, position) => setModal({ type: "deletePosition", coin, position }),
    sell: (coin, positionId) => setModal({ type: "sale", coin, positionId }),
    editSale: (coin, group) => setModal({ type: "sale", coin, group }),
    deleteSale: (coin, group) => setModal({ type: "deleteSale", coin, group }),
    reorder: async (coin, ids) => {
      // Od razu pokazujemy nową kolejność, potem zapis na serwerze.
      const order = new Map(ids.map((id, index) => [id, index]));
      setView((current) => current && {
        ...current,
        coins: current.coins.map((c) =>
          c.symbol === coin.symbol
            ? { ...c, positions: [...c.positions].sort((a, b) => order.get(a.id) - order.get(b.id)) }
            : c,
        ),
      });
      try {
        applyView(await portfoliosApi.reorderPositions(selectedId, ids));
      } catch (err) {
        setError(errorMessage(err, "Nie udało się zapisać kolejności"));
        portfoliosApi.get(selectedId).then(applyView).catch(() => {});
      }
    },
  };

  const selected = portfolios?.find((p) => p.id === selectedId) ?? null;
  const currentView = view && view.id === selectedId ? view : null;
  const closedCount = currentView?.coins.reduce((n, c) => n + c.closed_positions, 0) ?? 0;
  const visibleCoins = currentView?.coins.filter((c) => showClosed || c.open_positions > 0) ?? [];

  const renderModal = () => {
    if (!modal) return null;
    switch (modal.type) {
      case "createPortfolio":
        return (
          <NameDialog
            title="Nowy portfel"
            submitLabel="Utwórz"
            onClose={closeModal}
            onSubmit={async (name) => {
              const created = await portfoliosApi.create(name);
              setPortfolios((list) => [...(list ?? []), { ...created, positions_count: 0 }]);
              setSelectedId(created.id);
              setView(created);
            }}
          />
        );
      case "renamePortfolio":
        return (
          <NameDialog
            title="Zmień nazwę portfela"
            initial={selected?.name}
            onClose={closeModal}
            onSubmit={async (name) => applyView(await portfoliosApi.rename(selectedId, name))}
          />
        );
      case "deletePortfolio":
        return (
          <ConfirmDialog
            title="Usunąć portfel?"
            confirmLabel="Usuń portfel"
            onClose={closeModal}
            message={
              <>
                <p>
                  Portfel <strong className="text-zinc-100">{selected?.name}</strong> zostanie usunięty razem ze wszystkimi
                  pozycjami ({selected?.positions_count ?? 0}) i sprzedażami.
                </p>
                <p className="text-loss">Tej operacji nie można cofnąć.</p>
              </>
            }
            onConfirm={async () => {
              await portfoliosApi.remove(selectedId);
              setView(null);
              await loadList();
            }}
          />
        );
      case "position":
        return (
          <PositionForm
            position={modal.position}
            defaultSymbol={modal.symbol}
            onClose={closeModal}
            onSubmit={async (body) => {
              const data = modal.position
                ? await portfoliosApi.updatePosition(modal.position.id, body)
                : await portfoliosApi.addPosition(selectedId, body);
              applyView(data);
              setExpanded((current) => new Set(current).add(body.symbol));
            }}
          />
        );
      case "deletePosition":
        return (
          <ConfirmDialog
            title="Usunąć zakup?"
            onClose={closeModal}
            message={
              <p>
                Zakup <strong className="text-zinc-100">{fmtQty(modal.position.quantity)} {modal.coin.symbol}</strong> po $
                {fmtPrice(modal.position.buy_price)} z {fmtDate(modal.position.bought_at)}
                {modal.position.sales.length > 0 && ` oraz jego sprzedaże (${modal.position.sales.length})`} zostanie usunięty.
              </p>
            }
            onConfirm={async () => applyView(await portfoliosApi.removePosition(modal.position.id))}
          />
        );
      case "sale":
        return (
          <SaleForm
            coin={modal.coin}
            preselectId={modal.positionId}
            group={modal.group}
            onClose={closeModal}
            onSubmit={async (body) =>
              applyView(
                modal.group
                  ? await portfoliosApi.updateSale(modal.group.group_id, body)
                  : await portfoliosApi.addSale(selectedId, body),
              )
            }
          />
        );
      case "deleteSale":
        return (
          <ConfirmDialog
            title="Usunąć sprzedaż?"
            onClose={closeModal}
            message={
              <p>
                Sprzedaż <strong className="text-zinc-100">{fmtQty(modal.group.quantity)} {modal.coin.symbol}</strong> po $
                {fmtPrice(modal.group.price)} z {fmtDate(modal.group.sold_at)}
                {modal.group.parts.length > 1 && ` (z ${modal.group.parts.length} pozycji)`} zostanie usunięta, a ilość wróci do
                pozycji.
              </p>
            }
            onConfirm={async () => applyView(await portfoliosApi.removeSale(modal.group.group_id))}
          />
        );
      default:
        return null;
    }
  };

  // ------------------------------------------------------------- widok

  if (portfolios === null) {
    return error ? <ErrorBanner>{error}</ErrorBanner> : <p className="text-sm text-zinc-500">Ładowanie portfeli…</p>;
  }

  return (
    <div className="space-y-6">
      {/* Wybór portfela */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0">
          {portfolios.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setSelectedId(p.id)}
              className={`shrink-0 rounded-xl border px-3.5 py-2 text-left transition ${
                p.id === selectedId
                  ? "border-neon-violet/50 bg-neon-violet/10 shadow-neon-violet"
                  : "border-white/[0.06] bg-ink-900 hover:border-white/15"
              }`}
            >
              <div className="text-sm font-medium text-zinc-100">{p.name}</div>
              <div className="num text-[11px] text-zinc-500">{fmtMoney(p.summary.value)}</div>
            </button>
          ))}
          <button type="button" className="btn-ghost shrink-0 self-stretch" onClick={() => setModal({ type: "createPortfolio" })}>
            <PlusIcon size={16} /> Portfel
          </button>
        </div>

        {selected && (
          <div className="flex shrink-0 gap-1">
            <button type="button" className="btn-icon" title="Zmień nazwę" onClick={() => setModal({ type: "renamePortfolio" })}>
              <EditIcon size={16} />
            </button>
            <button type="button" className="btn-icon hover:text-loss" title="Usuń portfel" onClick={() => setModal({ type: "deletePortfolio" })}>
              <TrashIcon size={16} />
            </button>
          </div>
        )}
      </div>

      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      {portfolios.length === 0 ? (
        <EmptyState
          title="Nie masz jeszcze portfela"
          action={
            <button type="button" className="btn-primary" onClick={() => setModal({ type: "createPortfolio" })}>
              <PlusIcon size={16} /> Utwórz portfel
            </button>
          }
        >
          Portfel grupuje Twoje zakupy. Możesz mieć ich kilka, np. „Długoterminowy” i „Trading”.
        </EmptyState>
      ) : !currentView ? (
        <p className="text-sm text-zinc-500">Ładowanie portfela…</p>
      ) : (
        <>
          <SummaryCards summary={currentView.summary} />

          <div className="tile px-4 py-3">
            <PriceStatusBar />
          </div>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
                Coiny <span className="text-zinc-600">({visibleCoins.length})</span>
              </h2>
              <div className="flex flex-wrap justify-end gap-2">
                {closedCount > 0 && (
                  <button
                    type="button"
                    className={`btn-ghost ${showClosed ? "border-neon-violet/40 text-zinc-50" : ""}`}
                    onClick={() => setShowClosed((v) => !v)}
                    aria-pressed={showClosed}
                    title="Zamknięte pozycje są zawsze wliczone do zysku ogólnego"
                  >
                    <EyeIcon size={16} /> {showClosed ? "Ukryj zamknięte" : `Pokaż zamknięte (${closedCount})`}
                  </button>
                )}
                <button type="button" className="btn-primary" onClick={() => actions.addPosition()}>
                  <PlusIcon size={16} /> Dodaj zakup
                </button>
              </div>
            </div>

            {visibleCoins.length === 0 ? (
              currentView.coins.length > 0 ? (
                <EmptyState title="Wszystkie pozycje są zamknięte">
                  Kliknij „Pokaż zamknięte”, aby zobaczyć historię. Ich wynik jest wliczony do zysku ogólnego.
                </EmptyState>
              ) : (
                <EmptyState title="Portfel jest pusty">
                  Dodaj pierwszy zakup: coin, cenę, ilość, opłatę i datę. Każdy zakup jest osobną pozycją z własnym wynikiem.
                </EmptyState>
              )
            ) : (
              <>
                <div className="hidden grid-cols-[1.5fr_1fr_1.1fr_1fr_1fr_1.3fr_auto] gap-x-4 px-4 text-[10px] uppercase tracking-wider text-zinc-500 md:grid">
                  <span>Coin</span>
                  <span>Ilość</span>
                  <span title="Ważona ilością, która została na otwartych pozycjach">Śr. cena zakupu</span>
                  <span>Wartość</span>
                  <span>Zainwestowane</span>
                  <span className="text-right">Zysk / strata</span>
                  <span className="w-[18px]" />
                </div>
                <div className="space-y-3">
                  {visibleCoins.map((coin) => (
                    <CoinRow
                      key={coin.symbol}
                      coin={coin}
                      expanded={expanded.has(coin.symbol)}
                      onToggle={() => toggle(coin.symbol)}
                      actions={actions}
                      showClosed={showClosed}
                      sortMode={sortModes[coin.symbol] ?? "custom"}
                      onSortChange={(mode) => setSortModes((m) => ({ ...m, [coin.symbol]: mode }))}
                    />
                  ))}
                </div>
              </>
            )}
          </section>
        </>
      )}

      {renderModal()}
    </div>
  );
}
