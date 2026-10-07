import { forwardRef } from "react";
import { fmtDate, fmtDateTime, fmtMoney, fmtPrice, fmtQty, toNumber } from "../../lib/format";
import { EditIcon, GripIcon, SellIcon, TrashIcon } from "../icons";
import { Pnl } from "../ui";

function Stat({ label, children, className = "" }) {
  return (
    <div className={className}>
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 lg:hidden">{label}</div>
      <div className="num text-sm text-zinc-200">{children}</div>
    </div>
  );
}

/** Jeden zakup z osobnym wynikiem + jego sprzedaże. */
const PositionRow = forwardRef(function PositionRow(
  { position, symbol, saleGroups, dragging, handleProps, onSell, onEdit, onDelete, onEditSale, onDeleteSale },
  ref,
) {
  const closed = position.is_closed;
  const partiallySold = !closed && toNumber(position.sold_quantity) > 0;

  return (
    <div
      ref={ref}
      className={`rounded-xl border bg-ink-800/50 p-3 transition-[border-color,box-shadow,opacity] ${
        dragging ? "relative z-10 border-neon-violet/60 shadow-neon-violet" : "border-white/[0.05] hover:border-white/10"
      } ${closed && !dragging ? "opacity-70" : ""}`}
    >
      <div className="grid grid-cols-[auto_1fr_1fr] items-center gap-x-3 gap-y-3 sm:grid-cols-[auto_1fr_1fr_1fr] lg:grid-cols-[auto_1.1fr_1fr_1.2fr_1fr_1fr_1.4fr_auto] lg:gap-x-4">
        <button
          type="button"
          className="row-span-4 -ml-1 cursor-grab self-stretch rounded-md px-0.5 text-zinc-600 transition hover:bg-white/5 hover:text-zinc-300 active:cursor-grabbing sm:row-span-3 lg:row-span-1"
          title="Przeciągnij, aby zmienić kolejność"
          aria-label="Przeciągnij, aby zmienić kolejność"
          {...handleProps}
        >
          <GripIcon size={16} />
        </button>
        <Stat label="Data">
          <span className="font-sans">{fmtDate(position.bought_at)}</span>
          {(closed || partiallySold) && (
            <span className="mt-1 block">
              <span className="chip whitespace-nowrap">{closed ? "zamknięta" : "częściowo sprzedana"}</span>
            </span>
          )}
        </Stat>
        <Stat label="Cena zakupu">${fmtPrice(position.buy_price)}</Stat>
        <Stat label="Ilość (otwarta / na koncie)">
          {fmtQty(position.open_quantity)}
          {toNumber(position.open_quantity) !== toNumber(position.held_quantity) && (
            <span className="text-zinc-500"> / {fmtQty(position.held_quantity)}</span>
          )}
        </Stat>
        <Stat label="Koszt">{fmtMoney(position.cost)}</Stat>
        <Stat label="Wartość">{closed ? "—" : fmtMoney(position.value)}</Stat>
        <Stat label="Zysk / strata" className="lg:text-right">
          <Pnl value={position.total_pnl} pct={position.total_pnl_pct} />
          {toNumber(position.realized_pnl) !== 0 && !closed && (
            <div className="text-[11px] text-zinc-500">
              w tym zrealizowany: <span className="num">{fmtMoney(position.realized_pnl, { signed: true })}</span>
            </div>
          )}
        </Stat>
        <div className="col-span-2 flex justify-end gap-1 sm:col-span-3 lg:col-span-1">
          {!closed && (
            <button type="button" className="btn-icon hover:text-neon-green" title="Sprzedaj z tej pozycji" onClick={onSell}>
              <SellIcon size={16} />
            </button>
          )}
          <button type="button" className="btn-icon" title="Edytuj zakup" onClick={onEdit}>
            <EditIcon size={16} />
          </button>
          <button type="button" className="btn-icon hover:text-loss" title="Usuń zakup" onClick={onDelete}>
            <TrashIcon size={16} />
          </button>
        </div>
      </div>

      {(position.note || toNumber(position.fee_coin) > 0) && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 pl-7 text-xs text-zinc-500">
          {toNumber(position.fee_coin) > 0 && (
            <span>
              opłata: <span className="num">{fmtQty(position.fee_coin)} {symbol}</span>
            </span>
          )}
          {position.note && <span className="italic">„{position.note}”</span>}
        </div>
      )}

      {position.sales.length > 0 && (
        <ul className="mt-3 space-y-1.5 border-t border-white/[0.05] pl-7 pt-2">
          {position.sales.map((sale) => {
            const group = saleGroups.get(sale.group_id);
            const shared = group && group.parts.length > 1;
            return (
              <li key={sale.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-400">
                <span className="chip border-neon-green/20 text-neon-green/80">sprzedaż</span>
                <span>{fmtDateTime(sale.sold_at)}</span>
                <span className="num text-zinc-300">
                  {fmtQty(sale.quantity)} {symbol} × ${fmtPrice(sale.price)}
                </span>
                {toNumber(sale.fee_quote) > 0 && <span className="num">opłata {fmtMoney(sale.fee_quote)}</span>}
                {shared && (
                  <span className="chip" title="Ta sprzedaż obejmuje kilka pozycji">
                    część sprzedaży {fmtQty(group.quantity)} {symbol} z {group.parts.length} pozycji
                  </span>
                )}
                {sale.note && <span className="italic">„{sale.note}”</span>}
                <span className="ml-auto flex gap-1">
                  <button type="button" className="btn-icon h-7 w-7" title="Edytuj sprzedaż" onClick={() => onEditSale(sale.group_id)}>
                    <EditIcon size={14} />
                  </button>
                  <button type="button" className="btn-icon h-7 w-7 hover:text-loss" title="Usuń sprzedaż" onClick={() => onDeleteSale(sale.group_id)}>
                    <TrashIcon size={14} />
                  </button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
});

export default PositionRow;
