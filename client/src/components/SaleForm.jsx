import { useMemo, useState } from "react";
import { errorMessage } from "../api/client";
import { useQuoteCurrency } from "../context/contexts";
import { t } from "../i18n";
import * as dec from "../lib/decimal";
import { fmtDate, fmtMoney, fmtPct, fmtQty, fmtUnitPrice, parseAmount, pnlTone, toLocalInput, toNumber } from "../lib/format";
import Modal from "./Modal";
import { DecimalInput, Field, Pnl } from "./ui";

/**
 * Split the total quantity across the selected positions in selection order:
 * the first selected one gets as much as it has (or what's left), then the next one, etc.
 */
function distribute(total, selectedIds, available) {
  let remaining = total;
  const result = {};
  for (const id of selectedIds) {
    const take = dec.isPositive(remaining) ? dec.min(available[id], remaining) : "0";
    result[id] = take;
    remaining = dec.sub(remaining, take);
  }
  return result;
}

/**
 * A sale from one or several positions of the same coin.
 * - select positions (selection order = order in which they are "used up"),
 * - enter the total quantity -> it is split automatically; the per-position quantity can be edited manually.
 */
export default function SaleForm({ coin, preselectId = null, group = null, onSubmit, onClose }) {
  const currency = useQuoteCurrency();
  const editing = Boolean(group);
  const groupQty = useMemo(
    () => Object.fromEntries((group?.parts ?? []).map((p) => [p.position_id, p.quantity])),
    [group],
  );

  // Choices: open positions + (when editing) positions of this sale, even if already closed.
  const choices = useMemo(() => coin.positions.filter((p) => !p.is_closed || groupQty[p.id]), [coin, groupQty]);
  const available = useMemo(
    () => Object.fromEntries(choices.map((p) => [p.id, dec.add(p.open_quantity, groupQty[p.id] ?? "0")])),
    [choices, groupQty],
  );

  const [selected, setSelected] = useState(() =>
    editing ? group.parts.map((p) => p.position_id) : preselectId ? [preselectId] : [],
  );
  const [quantities, setQuantities] = useState(() => (editing ? { ...groupQty } : {}));
  const [total, setTotal] = useState(editing ? group.quantity : "");
  const [manual, setManual] = useState(editing);

  const [price, setPrice] = useState(group?.price ?? coin.price?.price ?? "");
  const [fee, setFee] = useState(group && toNumber(group.fee_quote) !== 0 ? group.fee_quote : "");
  const [soldAt, setSoldAt] = useState(toLocalInput(group?.sold_at ?? new Date()));
  const [exitReason, setExitReason] = useState(group?.exit_reason ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const selectedAvailable = dec.sum(selected.map((id) => available[id]));
  const totalAmount = parseAmount(total);
  const allocatedTotal = dec.sum(selected.map((id) => parseAmount(quantities[id] ?? "") ?? "0"));

  const applyTotal = (value, ids = selected) => {
    setTotal(value);
    setManual(false);
    const amount = parseAmount(value);
    setQuantities(amount ? distribute(amount, ids, available) : {});
  };

  const toggle = (id) => {
    const next = selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id];
    setSelected(next);
    if (!manual && totalAmount) {
      setQuantities(distribute(totalAmount, next, available));
    } else if (!selected.includes(id) && !totalAmount) {
      // No total entered: selecting a position means selling all of it.
      setQuantities((q) => ({ ...q, [id]: available[id] }));
      setManual(true);
    }
  };

  const setPositionQty = (id, value) => {
    setManual(true);
    setQuantities((q) => ({ ...q, [id]: value }));
  };

  const sellAll = () => {
    setManual(false);
    setTotal(selectedAvailable);
    setQuantities(Object.fromEntries(selected.map((id) => [id, available[id]])));
  };

  // Result preview (display only - the backend does the real calculation).
  const priceNumber = toNumber(parseAmount(price));
  const feeNumber = toNumber(parseAmount(fee || "0")) ?? 0;
  const allocatedNumber = toNumber(allocatedTotal) || 0;
  const preview = selected.map((id) => {
    const position = choices.find((p) => p.id === id);
    const qty = toNumber(parseAmount(quantities[id] ?? "")) ?? 0;
    const feePart = allocatedNumber > 0 ? (feeNumber * qty) / allocatedNumber : 0;
    const costShare = (toNumber(position.cost) * qty) / toNumber(position.held_quantity);
    const pnl = priceNumber === null ? null : qty * priceNumber - feePart - costShare;
    return { id, qty, pnl, pct: pnl === null || costShare === 0 ? null : (pnl / costShare) * 100 };
  });
  const previewPnl = preview.every((p) => p.pnl !== null) ? preview.reduce((acc, p) => acc + p.pnl, 0) : null;
  const proceeds = priceNumber === null ? null : allocatedNumber * priceNumber - feeNumber;

  const submit = async (e) => {
    e.preventDefault();
    const allocations = selected
      .map((id) => ({ position_id: id, quantity: parseAmount(quantities[id] ?? "") }))
      .filter((a) => a.quantity && dec.isPositive(a.quantity));
    const body = {
      price: parseAmount(price),
      fee_quote: parseAmount(fee || "0"),
      sold_at: soldAt,
      exit_reason: exitReason.trim() || null,
      allocations,
    };
    if (allocations.length === 0) return setError(t("sale.errors.nothingSelected"));
    if (selected.some((id) => quantities[id] && parseAmount(quantities[id]) === null)) {
      return setError(t("sale.errors.invalidQuantity"));
    }
    const tooMuch = allocations.find((a) => dec.cmp(a.quantity, available[a.position_id]) > 0);
    if (tooMuch) return setError(t("sale.errors.tooMuch", { amount: fmtQty(available[tooMuch.position_id]) }));
    if (!body.price || toNumber(body.price) <= 0) return setError(t("sale.errors.invalidPrice"));
    if (body.fee_quote === null) return setError(t("sale.errors.invalidFee"));

    setBusy(true);
    setError(null);
    try {
      await onSubmit(body);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  const shortage = totalAmount && !manual && dec.cmp(totalAmount, selectedAvailable) > 0;

  return (
    <Modal
      title={editing ? t("sale.editTitle", { symbol: coin.symbol }) : t("sale.newTitle", { symbol: coin.symbol })}
      onClose={onClose}
      wide
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field
            label={t("sale.totalQuantity", { symbol: coin.symbol })}
            htmlFor="sf-total"
            hint={
              selected.length > 0 ? (
                <button type="button" className="text-neon-green hover:underline" onClick={sellAll}>
                  {t("sale.sellAllSelected", { amount: fmtQty(selectedAvailable) })}
                </button>
              ) : (
                t("sale.selectPositionsHint")
              )
            }
          >
            <DecimalInput
              id="sf-total"
              value={manual ? allocatedTotal : total}
              onChange={(value) => applyTotal(value)}
              placeholder="0.0"
              autoFocus
            />
          </Field>
          <Field
            label={t("sale.price", { currency })}
            htmlFor="sf-price"
            hint={coin.price ? (
              <button type="button" className="text-neon-green hover:underline" onClick={() => setPrice(coin.price.price)}>
                {t("sale.useCurrent", { price: fmtUnitPrice(coin.price.price) })}
              </button>
            ) : undefined}
          >
            <DecimalInput id="sf-price" value={price} onChange={setPrice} />
          </Field>
          <Field label={t("sale.fee", { currency })} htmlFor="sf-fee" hint={t("sale.feeHint")}>
            <DecimalInput id="sf-fee" value={fee} onChange={setFee} placeholder="0" />
          </Field>
        </div>

        <div>
          <div className="label flex items-center justify-between">
            <span>{t("sale.positions")}</span>
            <span className="normal-case tracking-normal text-zinc-500">{t("sale.orderHint")}</span>
          </div>
          <div className="space-y-1.5">
            {choices.map((position) => {
              const order = selected.indexOf(position.id);
              const isSelected = order !== -1;
              const row = preview.find((p) => p.id === position.id);
              const date = fmtDate(position.bought_at);
              return (
                <div
                  key={position.id}
                  className={`grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2 rounded-xl border p-2.5 transition sm:grid-cols-[auto_1fr_auto_9rem] ${
                    isSelected ? "border-neon-green/40 bg-neon-green/[0.05]" : "border-white/[0.06] bg-ink-800/40 hover:border-white/15"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => toggle(position.id)}
                    className={`grid h-6 w-6 place-items-center rounded-md border text-[11px] font-bold transition ${
                      isSelected ? "border-neon-green bg-neon-green text-ink-950" : "border-white/20 text-transparent hover:border-white/40"
                    }`}
                    aria-pressed={isSelected}
                    aria-label={t("sale.selectPosition", { date })}
                  >
                    {isSelected ? order + 1 : ""}
                  </button>
                  <button type="button" onClick={() => toggle(position.id)} className="min-w-0 text-left">
                    <div className="text-sm text-zinc-200">
                      {date} · <span className="num">{fmtUnitPrice(position.buy_price)}</span>
                      {position.entry_reason && <span className="ml-2 text-xs italic text-zinc-500">{t("common.quoted", { text: position.entry_reason })}</span>}
                    </div>
                    <div className="num text-xs text-zinc-500">
                      {t("sale.available", { amount: fmtQty(available[position.id]) })} · {t("sale.now")}{" "}
                      <span className={pnlTone(position.total_pnl_pct)}>{fmtPct(position.total_pnl_pct)}</span>
                    </div>
                  </button>
                  <div className="col-span-2 text-right text-xs sm:col-span-1">
                    {isSelected && row?.pnl !== null && row?.qty > 0 && (
                      <span className={`num ${pnlTone(row.pnl)}`}>
                        {fmtMoney(row.pnl, { signed: true })} ({fmtPct(row.pct)})
                      </span>
                    )}
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <DecimalInput
                      value={quantities[position.id] ?? ""}
                      onChange={(value) => setPositionQty(position.id, value)}
                      disabled={!isSelected}
                      placeholder={isSelected ? "0" : "—"}
                      aria-label={t("sale.quantityFor", { date })}
                      className="py-1.5 text-sm"
                    />
                  </div>
                </div>
              );
            })}
          </div>
          {shortage && (
            <p className="mt-2 text-xs text-amber-300">
              {t("sale.shortage", { amount: fmtQty(selectedAvailable), symbol: coin.symbol })}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t("sale.date")} htmlFor="sf-date">
            <input id="sf-date" type="datetime-local" className="w-full" value={soldAt}
              onChange={(e) => setSoldAt(e.target.value)} required />
          </Field>
          <Field label={t("sale.exitReason")} htmlFor="sf-reason">
            <input id="sf-reason" className="w-full" maxLength={4000} value={exitReason} onChange={(e) => setExitReason(e.target.value)} />
          </Field>
        </div>

        <div className="grid grid-cols-3 gap-2 rounded-xl border border-white/[0.06] bg-ink-800/60 p-3 text-xs">
          <div>
            <div className="muted">{t("sale.preview.selling")}</div>
            <div className="num text-sm text-zinc-200">{fmtQty(allocatedTotal)} {coin.symbol}</div>
          </div>
          <div>
            <div className="muted">{t("sale.preview.proceeds")}</div>
            <div className="num text-sm text-zinc-200">{proceeds === null || !allocatedNumber ? "—" : fmtMoney(proceeds)}</div>
          </div>
          <div className="text-right">
            <div className="muted">{t("sale.preview.pnl")}</div>
            <div className="text-sm">{previewPnl !== null && allocatedNumber ? <Pnl value={previewPnl} /> : "—"}</div>
          </div>
        </div>

        {error && <p className="text-sm text-loss">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>{t("common.actions.cancel")}</button>
          <button type="submit" className="btn-green" disabled={busy}>
            {busy ? t("common.actions.saving") : editing ? t("common.actions.saveChanges") : t("sale.submitNew")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
