import { useMemo, useState } from "react";
import { errorMessage } from "../api/client";
import * as dec from "../lib/decimal";
import { fmtDate, fmtMoney, fmtPct, fmtPrice, fmtQty, parseAmount, pnlTone, toLocalInput, toNumber } from "../lib/format";
import Modal from "./Modal";
import { DecimalInput, Field, Pnl } from "./ui";

/**
 * Rozdziela łączną ilość na zaznaczone pozycje w kolejności zaznaczania:
 * pierwsza zaznaczona dostaje tyle, ile ma (lub ile zostało), potem kolejna itd.
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
 * Sprzedaż z jednej lub kilku pozycji tego samego coina.
 * - zaznacz pozycje (kolejność zaznaczania = kolejność "zużywania"),
 * - wpisz łączną ilość -> rozdzieli się automatycznie; ilość przy pozycji można poprawić ręcznie.
 */
export default function SaleForm({ coin, preselectId = null, group = null, onSubmit, onClose }) {
  const editing = Boolean(group);
  const groupQty = useMemo(
    () => Object.fromEntries((group?.parts ?? []).map((p) => [p.position_id, p.quantity])),
    [group],
  );

  // Do wyboru: otwarte pozycje + (przy edycji) pozycje z tej sprzedaży, nawet jeśli już zamknięte.
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
  const [note, setNote] = useState(group?.note ?? "");
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
      // Bez wpisanej ilości: zaznaczenie = sprzedaj całą pozycję.
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

  // Podgląd wyniku (tylko wyświetlanie - właściwe liczenie robi backend).
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
      note: note.trim() || null,
      allocations,
    };
    if (allocations.length === 0) return setError("Zaznacz pozycje i podaj ilość do sprzedaży");
    if (selected.some((id) => quantities[id] && parseAmount(quantities[id]) === null)) {
      return setError("Popraw ilość przy zaznaczonych pozycjach");
    }
    const tooMuch = allocations.find((a) => dec.cmp(a.quantity, available[a.position_id]) > 0);
    if (tooMuch) return setError(`Z jednej z pozycji chcesz sprzedać więcej niż ${fmtQty(available[tooMuch.position_id])}`);
    if (!body.price || toNumber(body.price) <= 0) return setError("Podaj poprawną cenę sprzedaży");
    if (body.fee_quote === null) return setError("Podaj poprawną opłatę (lub zostaw puste)");

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
    <Modal title={editing ? `Edycja sprzedaży ${coin.symbol}` : `Sprzedaż ${coin.symbol}`} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field
            label={`Ilość łącznie (${coin.symbol})`}
            htmlFor="sf-total"
            hint={
              selected.length > 0 ? (
                <button type="button" className="text-neon-green hover:underline" onClick={sellAll}>
                  Całe zaznaczone: {fmtQty(selectedAvailable)}
                </button>
              ) : (
                "Zaznacz pozycje poniżej"
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
            label="Cena sprzedaży (USDT)"
            htmlFor="sf-price"
            hint={coin.price ? (
              <button type="button" className="text-neon-green hover:underline" onClick={() => setPrice(coin.price.price)}>
                Użyj aktualnej: ${fmtPrice(coin.price.price)}
              </button>
            ) : undefined}
          >
            <DecimalInput id="sf-price" value={price} onChange={setPrice} />
          </Field>
          <Field label="Opłata łącznie (USDT)" htmlFor="sf-fee" hint="Rozdzielana proporcjonalnie do ilości.">
            <DecimalInput id="sf-fee" value={fee} onChange={setFee} placeholder="0" />
          </Field>
        </div>

        <div>
          <div className="label flex items-center justify-between">
            <span>Z których pozycji</span>
            <span className="normal-case tracking-normal text-zinc-500">kolejność zaznaczania = kolejność rozdziału</span>
          </div>
          <div className="space-y-1.5">
            {choices.map((position) => {
              const order = selected.indexOf(position.id);
              const isSelected = order !== -1;
              const row = preview.find((p) => p.id === position.id);
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
                    aria-label={`Zaznacz pozycję z ${fmtDate(position.bought_at)}`}
                  >
                    {isSelected ? order + 1 : ""}
                  </button>
                  <button type="button" onClick={() => toggle(position.id)} className="min-w-0 text-left">
                    <div className="text-sm text-zinc-200">
                      {fmtDate(position.bought_at)} · <span className="num">${fmtPrice(position.buy_price)}</span>
                      {position.note && <span className="ml-2 text-xs italic text-zinc-500">„{position.note}”</span>}
                    </div>
                    <div className="num text-xs text-zinc-500">
                      dostępne {fmtQty(available[position.id])} · teraz{" "}
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
                      aria-label={`Ilość z pozycji ${fmtDate(position.bought_at)}`}
                      className="py-1.5 text-sm"
                    />
                  </div>
                </div>
              );
            })}
          </div>
          {shortage && (
            <p className="mt-2 text-xs text-amber-300">
              Zaznaczone pozycje mają razem tylko {fmtQty(selectedAvailable)} {coin.symbol}. Zaznacz kolejną pozycję albo zmniejsz ilość.
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Data sprzedaży" htmlFor="sf-date">
            <input id="sf-date" type="datetime-local" className="w-full" value={soldAt}
              onChange={(e) => setSoldAt(e.target.value)} required />
          </Field>
          <Field label="Notatka (opcjonalnie)" htmlFor="sf-note">
            <input id="sf-note" className="w-full" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </div>

        <div className="grid grid-cols-3 gap-2 rounded-xl border border-white/[0.06] bg-ink-800/60 p-3 text-xs">
          <div>
            <div className="muted">Sprzedajesz</div>
            <div className="num text-sm text-zinc-200">{fmtQty(allocatedTotal)} {coin.symbol}</div>
          </div>
          <div>
            <div className="muted">Przychód po opłacie</div>
            <div className="num text-sm text-zinc-200">{proceeds === null || !allocatedNumber ? "—" : fmtMoney(proceeds)}</div>
          </div>
          <div className="text-right">
            <div className="muted">Zysk na tej sprzedaży</div>
            <div className="text-sm">{previewPnl !== null && allocatedNumber ? <Pnl value={previewPnl} /> : "—"}</div>
          </div>
        </div>

        {error && <p className="text-sm text-loss">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Anuluj</button>
          <button type="submit" className="btn-green" disabled={busy}>
            {busy ? "Zapisywanie…" : editing ? "Zapisz zmiany" : "Zapisz sprzedaż"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
