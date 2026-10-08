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
import { t } from "../i18n";
import Trans from "../i18n/Trans";
import { fmtDate, fmtMoney, fmtQty, fmtUnitPrice } from "../lib/format";

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
  // Closed positions hidden by default; sorting remembered separately for each coin.
  const [showClosed, setShowClosed] = useState(() => readJson(SHOW_CLOSED_KEY, false));
  const [sortModes, setSortModes] = useState(() => readJson(SORT_KEY, {}));

  useEffect(() => localStorage.setItem(SHOW_CLOSED_KEY, JSON.stringify(showClosed)), [showClosed]);
  useEffect(() => localStorage.setItem(SORT_KEY, JSON.stringify(sortModes)), [sortModes]);

  // ------------------------------------------------------------- loading

  const loadList = useCallback(async () => {
    try {
      const list = await portfoliosApi.list();
      setPortfolios(list);
      setSelectedId((current) => (list.some((p) => p.id === current) ? current : list[0]?.id ?? null));
    } catch (err) {
      setError(errorMessage(err, "portfolio.page.loadListFailed"));
    }
  }, []);

  useEffect(() => {
    loadList();
    // e.g. after "Synchronizuj" - refresh the list without reloading the page
    window.addEventListener("portfolios:changed", loadList);
    return () => window.removeEventListener("portfolios:changed", loadList);
  }, [loadList]);

  useEffect(() => {
    if (selectedId) localStorage.setItem(SELECTED_KEY, String(selectedId));
  }, [selectedId]);

  // Portfolio view: reloaded when the portfolio changes and when the backend has new prices (no exchange calls).
  useEffect(() => {
    if (!selectedId) {
      setView(null);
      return undefined;
    }
    let cancelled = false;
    portfoliosApi
      .get(selectedId)
      .then((data) => !cancelled && setView(data))
      .catch((err) => !cancelled && setError(errorMessage(err, "portfolio.page.loadFailed")));
    return () => {
      cancelled = true;
    };
  }, [selectedId, version]);

  /** Every change returns the recalculated portfolio - replace the view and the summary in the list. */
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

  // ------------------------------------------------------------- actions

  const actions = {
    addPosition: (symbol = "") => setModal({ type: "position", symbol }),
    editPosition: (position) => setModal({ type: "position", position }),
    deletePosition: (coin, position) => setModal({ type: "deletePosition", coin, position }),
    sell: (coin, positionId) => setModal({ type: "sale", coin, positionId }),
    editSale: (coin, group) => setModal({ type: "sale", coin, group }),
    deleteSale: (coin, group) => setModal({ type: "deleteSale", coin, group }),
    reorder: async (coin, ids) => {
      // Show the new order immediately, then save it on the server.
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
        setError(errorMessage(err, "portfolio.page.saveOrderFailed"));
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
            title={t("portfolio.dialogs.createTitle")}
            submitLabel={t("common.actions.create")}
            onClose={closeModal}
            onSubmit={async (name) => {
              const created = await portfoliosApi.create(name);
              setPortfolios((list) => [...(list ?? []), { ...created, kind: "manual", positions_count: 0 }]);
              setSelectedId(created.id);
              setView(created);
            }}
          />
        );
      case "renamePortfolio":
        return (
          <NameDialog
            title={t("portfolio.dialogs.renameTitle")}
            initial={selected?.name}
            onClose={closeModal}
            onSubmit={async (name) => applyView(await portfoliosApi.rename(selectedId, name))}
          />
        );
      case "deletePortfolio":
        return (
          <ConfirmDialog
            title={t("portfolio.dialogs.deleteTitle")}
            confirmLabel={t("portfolio.dialogs.deleteConfirm")}
            onClose={closeModal}
            message={
              <>
                <p>
                  <Trans
                    k="portfolio.dialogs.deleteMessage"
                    values={{ name: <strong className="text-zinc-100">{selected?.name}</strong>, count: selected?.positions_count ?? 0 }}
                  />
                </p>
                <p className="text-loss">{t("portfolio.dialogs.deleteWarning")}</p>
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
            title={t("portfolio.dialogs.deletePositionTitle")}
            onClose={closeModal}
            message={
              <>
                <p>
                  <Trans
                    k="portfolio.dialogs.deletePositionMessage"
                    values={{
                      amount: <strong className="text-zinc-100">{fmtQty(modal.position.quantity)} {modal.coin.symbol}</strong>,
                      price: fmtUnitPrice(modal.position.buy_price),
                      date: fmtDate(modal.position.bought_at),
                    }}
                  />
                </p>
                {modal.position.sales.length > 0 && (
                  <p>{t("portfolio.dialogs.deletePositionSales", { count: modal.position.sales.length })}</p>
                )}
              </>
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
            title={t("portfolio.dialogs.deleteSaleTitle")}
            onClose={closeModal}
            message={
              <>
                <p>
                  <Trans
                    k="portfolio.dialogs.deleteSaleMessage"
                    values={{
                      amount: <strong className="text-zinc-100">{fmtQty(modal.group.quantity)} {modal.coin.symbol}</strong>,
                      price: fmtUnitPrice(modal.group.price),
                      date: fmtDate(modal.group.sold_at),
                    }}
                  />
                </p>
                {modal.group.parts.length > 1 && (
                  <p>{t("portfolio.dialogs.deleteSaleShared", { count: modal.group.parts.length })}</p>
                )}
              </>
            }
            onConfirm={async () => applyView(await portfoliosApi.removeSale(modal.group.group_id))}
          />
        );
      default:
        return null;
    }
  };

  // ------------------------------------------------------------- view

  if (portfolios === null) {
    return error ? <ErrorBanner>{error}</ErrorBanner> : <p className="text-sm text-zinc-500">{t("portfolio.page.loadingList")}</p>;
  }

  return (
    <div className="space-y-6">
      {/* Portfolio selector */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          {[["import", t("portfolio.page.imported")], ["manual", t("portfolio.page.manual")]].map(([kind, label]) => {
            const list = portfolios.filter((p) => (p.kind ?? "manual") === kind);
            if (!list.length && kind === "import") return null;
            return (
              <div key={kind} className="flex items-center gap-2">
                <span className="w-24 shrink-0 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">{label}</span>
                <div className="-mr-4 flex min-w-0 gap-2 overflow-x-auto pb-1 pr-4 sm:mr-0 sm:flex-wrap sm:pr-0">
                  {list.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setSelectedId(p.id)}
                      className={`shrink-0 rounded-xl border px-3.5 py-2 text-left transition ${
                        p.kind === "import"
                          ? p.id === selectedId
                            ? "border-neon-blue/70 bg-neon-blue/10 shadow-neon-blue"
                            : "border-neon-blue/30 bg-ink-900 hover:border-neon-blue/60"
                          : p.id === selectedId
                            ? "border-neon-violet/50 bg-neon-violet/10 shadow-neon-violet"
                            : "border-white/[0.06] bg-ink-900 hover:border-white/15"
                      }`}
                    >
                      <div className="flex items-center gap-1.5 text-sm font-medium text-zinc-100">
                        {p.name}
                        {p.kind === "import" && (
                          <span className="rounded bg-neon-blue/15 px-1 text-[9px] font-semibold uppercase tracking-wider text-neon-blue">
                            {p.source}
                          </span>
                        )}
                      </div>
                      <div className="num text-[11px] text-zinc-500">{fmtMoney(p.summary.value)}</div>
                    </button>
                  ))}
                  {kind === "manual" && (
                    <button type="button" className="btn-ghost shrink-0 self-stretch" onClick={() => setModal({ type: "createPortfolio" })}>
                      <PlusIcon size={16} /> {t("portfolio.page.newPortfolio")}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {selected && (
          <div className="flex shrink-0 gap-1">
            <button type="button" className="btn-icon" title={t("portfolio.page.rename")} onClick={() => setModal({ type: "renamePortfolio" })}>
              <EditIcon size={16} />
            </button>
            <button type="button" className="btn-icon hover:text-loss" title={t("portfolio.page.delete")} onClick={() => setModal({ type: "deletePortfolio" })}>
              <TrashIcon size={16} />
            </button>
          </div>
        )}
      </div>

      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>

      {portfolios.length === 0 ? (
        <EmptyState
          title={t("portfolio.empty.noPortfolioTitle")}
          action={
            <button type="button" className="btn-primary" onClick={() => setModal({ type: "createPortfolio" })}>
              <PlusIcon size={16} /> {t("portfolio.empty.createPortfolio")}
            </button>
          }
        >
          {t("portfolio.empty.noPortfolioText")}
        </EmptyState>
      ) : !currentView ? (
        <p className="text-sm text-zinc-500">{t("portfolio.page.loadingOne")}</p>
      ) : (
        <>
          <SummaryCards summary={currentView.summary} />

          <div className="tile px-4 py-3">
            <PriceStatusBar />
          </div>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
                {t("portfolio.page.coins")} <span className="text-zinc-600">({visibleCoins.length})</span>
              </h2>
              <div className="flex flex-wrap justify-end gap-2">
                {closedCount > 0 && (
                  <button
                    type="button"
                    className={`btn-ghost ${showClosed ? "border-neon-violet/40 text-zinc-50" : ""}`}
                    onClick={() => setShowClosed((v) => !v)}
                    aria-pressed={showClosed}
                    title={t("portfolio.page.closedHint")}
                  >
                    <EyeIcon size={16} /> {showClosed ? t("portfolio.page.hideClosed") : t("portfolio.page.showClosed", { count: closedCount })}
                  </button>
                )}
                <button type="button" className="btn-primary" onClick={() => actions.addPosition()}>
                  <PlusIcon size={16} /> {t("portfolio.page.addPosition")}
                </button>
              </div>
            </div>

            {visibleCoins.length === 0 ? (
              currentView.coins.length > 0 ? (
                <EmptyState title={t("portfolio.empty.allClosedTitle")}>{t("portfolio.empty.allClosedText")}</EmptyState>
              ) : (
                <EmptyState title={t("portfolio.empty.emptyTitle")}>{t("portfolio.empty.emptyText")}</EmptyState>
              )
            ) : (
              <>
                <div className="hidden grid-cols-[1.5fr_1fr_1.1fr_1fr_1fr_1.3fr_auto] gap-x-4 px-4 text-[10px] uppercase tracking-wider text-zinc-500 md:grid">
                  <span>{t("portfolio.columns.coin")}</span>
                  <span>{t("portfolio.columns.quantity")}</span>
                  <span title={t("portfolio.columns.avgBuyPriceHint")}>{t("portfolio.columns.avgBuyPrice")}</span>
                  <span>{t("portfolio.columns.value")}</span>
                  <span>{t("portfolio.columns.invested")}</span>
                  <span className="text-right">{t("portfolio.columns.pnl")}</span>
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
