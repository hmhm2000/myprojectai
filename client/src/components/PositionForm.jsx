import { useState } from "react";
import { errorMessage } from "../api/client";
import { usePrices } from "../context/contexts";
import { fmtMoney, fmtPrice, fmtQty, parseAmount, previewMultiply, toLocalInput, toNumber } from "../lib/format";
import CoinPicker from "./CoinPicker";
import Modal from "./Modal";
import { DecimalInput, Field, Pnl } from "./ui";

/** Dodanie lub edycja zakupu (pozycji). */
export default function PositionForm({ position = null, defaultSymbol = "", onSubmit, onClose }) {
  const { prices } = usePrices();
  const editing = Boolean(position);
  const symbolLocked = editing && position.sales.length > 0;

  const [symbol, setSymbol] = useState(position?.symbol ?? defaultSymbol);
  const [buyPrice, setBuyPrice] = useState(position?.buy_price ?? "");
  const [quantity, setQuantity] = useState(position?.quantity ?? "");
  const [fee, setFee] = useState(position && toNumber(position.fee_coin) !== 0 ? position.fee_coin : "");
  const [boughtAt, setBoughtAt] = useState(toLocalInput(position?.bought_at ?? new Date()));
  const [note, setNote] = useState(position?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const quote = symbol ? prices[symbol] : null;
  const cost = previewMultiply(buyPrice, quantity);
  const held = toNumber(parseAmount(quantity)) !== null
    ? toNumber(parseAmount(quantity)) - (toNumber(parseAmount(fee || "0")) ?? 0)
    : null;
  const value = quote && held !== null ? held * toNumber(quote.price) : null;

  const submit = async (e) => {
    e.preventDefault();
    const body = {
      symbol,
      buy_price: parseAmount(buyPrice),
      quantity: parseAmount(quantity),
      fee_coin: parseAmount(fee || "0"),
      bought_at: boughtAt,
      note: note.trim() || null,
    };
    if (!body.symbol) return setError("Wybierz coina");
    if (!body.buy_price || toNumber(body.buy_price) <= 0) return setError("Podaj poprawną cenę zakupu");
    if (!body.quantity || toNumber(body.quantity) <= 0) return setError("Podaj poprawną ilość");
    if (body.fee_coin === null) return setError("Podaj poprawną opłatę (lub zostaw puste)");
    if (toNumber(body.fee_coin) >= toNumber(body.quantity)) return setError("Opłata musi być mniejsza niż ilość");

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

  return (
    <Modal title={editing ? `Edycja zakupu ${position.symbol}` : "Nowy zakup"} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Coin" htmlFor="pf-symbol" hint={symbolLocked ? "Pozycja ma sprzedaże, więc coina nie można zmienić." : undefined}>
          <CoinPicker id="pf-symbol" value={symbol} onChange={setSymbol} disabled={symbolLocked} autoFocus={!editing && !defaultSymbol} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field
            label="Cena zakupu (USDT)"
            htmlFor="pf-price"
            hint={
              quote ? (
                <button type="button" className="text-neon-green hover:underline" onClick={() => setBuyPrice(quote.price)}>
                  Użyj aktualnej: ${fmtPrice(quote.price)}
                </button>
              ) : undefined
            }
          >
            <DecimalInput id="pf-price" value={buyPrice} onChange={setBuyPrice} placeholder="0.00" autoFocus={Boolean(defaultSymbol) && !editing} />
          </Field>
          <Field label="Ilość (kupiona)" htmlFor="pf-qty">
            <DecimalInput id="pf-qty" value={quantity} onChange={setQuantity} placeholder="0.0" />
          </Field>
          <Field label={`Opłata (w ${symbol || "coinie"})`} htmlFor="pf-fee" hint="Jak na giełdzie: opłata pobrana z kupionej ilości.">
            <DecimalInput id="pf-fee" value={fee} onChange={setFee} placeholder="0" />
          </Field>
          <Field label="Data zakupu" htmlFor="pf-date">
            <input id="pf-date" type="datetime-local" className="w-full" value={boughtAt}
              onChange={(e) => setBoughtAt(e.target.value)} required />
          </Field>
        </div>

        <Field label="Notatka (opcjonalnie)" htmlFor="pf-note">
          <textarea id="pf-note" className="w-full" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        <div className="grid grid-cols-3 gap-2 rounded-xl border border-white/[0.06] bg-ink-800/60 p-3 text-xs">
          <div>
            <div className="muted">Koszt</div>
            <div className="num text-sm text-zinc-200">{cost === null ? "—" : fmtMoney(cost)}</div>
          </div>
          <div>
            <div className="muted">Na koncie</div>
            <div className="num text-sm text-zinc-200">{held === null ? "—" : fmtQty(held)}</div>
          </div>
          <div className="text-right">
            <div className="muted">Wynik teraz</div>
            <div className="text-sm">{value !== null && cost !== null ? <Pnl value={value - cost} /> : "—"}</div>
          </div>
        </div>

        {error && <p className="text-sm text-loss">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Anuluj</button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Zapisywanie…" : editing ? "Zapisz zmiany" : "Dodaj zakup"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
