import { useMemo } from "react";
import { fmtMoney, fmtPrice, fmtQty, toNumber } from "../../lib/format";
import { SORT_OPTIONS, sortPositions } from "../../lib/positionSort";
import { collectSaleGroups } from "../../lib/saleGroups";
import { ChevronIcon, PlusIcon, SellIcon } from "../icons";
import { Change24h, CoinBadge, Pnl } from "../ui";
import PositionRow from "./PositionRow";
import { useDragSort } from "./useDragSort";

const SOURCE_NAMES = { okx: "OKX", bybit: "Bybit" };

function Cell({ label, children, className = "" }) {
  return (
    <div className={className}>
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 md:hidden">{label}</div>
      {children}
    </div>
  );
}

/** Coin w portfelu (suma pozycji); po rozwinięciu lista zakupów z osobnym wynikiem. */
export default function CoinRow({ coin, expanded, onToggle, actions, showClosed, sortMode, onSortChange }) {
  const onlyClosed = coin.open_positions === 0;
  const saleGroups = useMemo(() => collectSaleGroups(coin), [coin]);

  const visible = useMemo(
    () => sortPositions(showClosed ? coin.positions : coin.positions.filter((p) => !p.is_closed), sortMode),
    [coin, showClosed, sortMode],
  );
  const byId = useMemo(() => new Map(coin.positions.map((p) => [p.id, p])), [coin]);
  const hiddenClosed = showClosed ? 0 : coin.closed_positions;

  // Przeciągnięcie zapisuje widoczną kolejność jako "własną"; ukryte (zamknięte) zostają na końcu.
  const { orderedIds, draggingId, register, handleProps } = useDragSort(
    visible.map((p) => p.id),
    (ids) => {
      const hidden = coin.positions.filter((p) => !ids.includes(p.id)).map((p) => p.id);
      onSortChange("custom");
      actions.reorder(coin, [...ids, ...hidden]);
    },
  );

  return (
    <div className={`tile ${expanded ? "glow glow-strong" : "glow"} overflow-visible`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="grid w-full grid-cols-2 items-center gap-x-4 gap-y-3 p-4 text-left md:grid-cols-[1.5fr_1fr_1.1fr_1fr_1fr_1.3fr_auto]"
      >
        <div className="col-span-2 flex items-center gap-3 md:col-span-1">
          <CoinBadge symbol={coin.symbol} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-zinc-50">{coin.symbol}</span>
              {coin.price && <span className="chip">{SOURCE_NAMES[coin.price.source] ?? coin.price.source}</span>}
            </div>
            <div className="flex items-center gap-2 text-sm">
              {coin.price ? (
                <>
                  <span className="num text-zinc-300">${fmtPrice(coin.price.price)}</span>
                  <Change24h value={coin.price.change_24h_pct} />
                </>
              ) : (
                <span className="text-xs text-amber-300">brak ceny</span>
              )}
            </div>
          </div>
          <ChevronIcon className={`ml-auto shrink-0 text-zinc-500 transition-transform duration-300 md:hidden ${expanded ? "rotate-180" : ""}`} />
        </div>

        <Cell label="Ilość">
          <span className="num text-zinc-200">{onlyClosed ? "0" : fmtQty(coin.open_quantity)}</span>
          <div className="text-[11px] text-zinc-500">
            {coin.open_positions} otw.{coin.closed_positions > 0 && ` · ${coin.closed_positions} zamk.`}
          </div>
        </Cell>
        <Cell label="Śr. cena zakupu">
          <span className="num text-zinc-200">{coin.avg_buy_price ? `$${fmtPrice(coin.avg_buy_price)}` : "—"}</span>
          {coin.break_even_price && coin.break_even_price !== coin.avg_buy_price && (
            <div className="num text-[11px] text-zinc-500" title="Koszt otwartej części / ilość - z opłatą pobraną w coinie">
              z opłatą ${fmtPrice(coin.break_even_price)}
            </div>
          )}
        </Cell>
        <Cell label="Wartość">
          <span className="num text-zinc-100">{fmtMoney(coin.value)}</span>
        </Cell>
        <Cell label="Zainwestowane">
          <span className="num text-zinc-400">{fmtMoney(coin.invested)}</span>
        </Cell>
        <Cell label="Zysk / strata" className="md:text-right">
          {onlyClosed ? (
            <div>
              <Pnl value={coin.total_pnl} pct={coin.total_pnl_pct} stacked />
              <div className="text-[11px] text-zinc-500">zamknięte</div>
            </div>
          ) : (
            <div>
              <Pnl value={coin.unrealized_pnl} pct={coin.unrealized_pnl_pct} stacked />
              {toNumber(coin.realized_pnl) !== 0 && (
                <div className="text-[11px] text-zinc-500">
                  ogólny: <Pnl value={coin.total_pnl} className="text-[11px]" />
                </div>
              )}
            </div>
          )}
        </Cell>
        <ChevronIcon className={`hidden text-zinc-500 transition-transform duration-300 md:block ${expanded ? "rotate-180" : ""}`} />
      </button>

      <div className={`collapsible ${expanded ? "open" : ""}`}>
        <div>
          <div className="space-y-2 border-t border-white/[0.05] px-3 pb-3 pt-3 sm:px-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="flex items-center gap-2 text-xs text-zinc-500">
                Sortuj
                <select
                  className="py-1 text-xs"
                  value={sortMode}
                  onChange={(e) => onSortChange(e.target.value)}
                >
                  {SORT_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              <span className="text-[11px] text-zinc-600">
                {hiddenClosed > 0 && `${hiddenClosed} zamkniętych ukrytych · `}przeciągnij ⠿, aby ustawić własną kolejność
              </span>
            </div>

            <div className="hidden grid-cols-[auto_1.1fr_1fr_1.2fr_1fr_1fr_1.4fr_auto] gap-x-4 px-3 text-[10px] uppercase tracking-wider text-zinc-500 lg:grid">
              <span className="w-4" />
              <span>Data zakupu</span>
              <span>Cena zakupu</span>
              <span>Ilość otwarta / na koncie</span>
              <span>Koszt</span>
              <span>Wartość</span>
              <span className="text-right">Zysk / strata</span>
              <span className="w-[6.5rem]" />
            </div>

            {orderedIds.map((id) => {
              const position = byId.get(id);
              return (
                <PositionRow
                  key={id}
                  ref={register(id)}
                  position={position}
                  symbol={coin.symbol}
                  saleGroups={saleGroups}
                  dragging={draggingId === id}
                  handleProps={handleProps(id)}
                  onSell={() => actions.sell(coin, position.id)}
                  onEdit={() => actions.editPosition(position)}
                  onDelete={() => actions.deletePosition(coin, position)}
                  onEditSale={(groupId) => actions.editSale(coin, saleGroups.get(groupId))}
                  onDeleteSale={(groupId) => actions.deleteSale(coin, saleGroups.get(groupId))}
                />
              );
            })}
            {visible.length === 0 && (
              <p className="px-1 py-2 text-xs text-zinc-500">Wszystkie pozycje są zamknięte i ukryte.</p>
            )}

            <div className="flex flex-wrap justify-end gap-2 pt-1">
              {!onlyClosed && (
                <button type="button" className="btn-ghost text-xs" onClick={() => actions.sell(coin, null)}>
                  <SellIcon size={14} /> Sprzedaj {coin.symbol}
                </button>
              )}
              <button type="button" className="btn-ghost text-xs" onClick={() => actions.addPosition(coin.symbol)}>
                <PlusIcon size={14} /> Kup {coin.symbol}
              </button>
            </div>
            {toNumber(coin.realized_pnl) !== 0 && (
              <p className="px-1 text-right text-xs text-zinc-500">
                Zrealizowany na {coin.symbol} (też z zamkniętych): <Pnl value={coin.realized_pnl} />
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
