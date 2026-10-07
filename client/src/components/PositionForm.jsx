import { useState } from "react";
import { errorMessage } from "../api/client";
import { usePrices, useQuoteCurrency } from "../context/contexts";
import { t } from "../i18n";
import { fmtMoney, fmtQty, fmtUnitPrice, parseAmount, previewMultiply, toLocalInput, toNumber } from "../lib/format";
import CoinPicker from "./CoinPicker";
import Modal from "./Modal";
import { DecimalInput, Field, Pnl } from "./ui";

/** Add or edit a purchase (position). */
export default function PositionForm({ position = null, defaultSymbol = "", onSubmit, onClose }) {
  const { prices } = usePrices();
  const currency = useQuoteCurrency();
  const editing = Boolean(position);
  const symbolLocked = editing && position.sales.length > 0;

  const [symbol, setSymbol] = useState(position?.symbol ?? defaultSymbol);
  const [buyPrice, setBuyPrice] = useState(position?.buy_price ?? "");
  const [quantity, setQuantity] = useState(position?.quantity ?? "");
  const [fee, setFee] = useState(position && toNumber(position.fee_coin) !== 0 ? position.fee_coin : "");
  const [boughtAt, setBoughtAt] = useState(toLocalInput(position?.bought_at ?? new Date()));
  const [entryReason, setEntryReason] = useState(position?.entry_reason ?? "");
  const [tags, setTags] = useState((position?.tags ?? []).join(", "));
  const [plan, setPlan] = useState(position?.plan ?? "");
  const [targetPrice, setTargetPrice] = useState(position?.target_price ?? "");
  const [stopLoss, setStopLoss] = useState(position?.stop_loss ?? "");
  const [showOnChart, setShowOnChart] = useState(position?.show_on_chart ?? true);
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
      entry_reason: entryReason.trim() || null,
      tags: tags.split(/[,;\s]+/).filter(Boolean),
      plan: plan.trim() || null,
      target_price: targetPrice.trim() ? parseAmount(targetPrice) : null,
      stop_loss: stopLoss.trim() ? parseAmount(stopLoss) : null,
      show_on_chart: showOnChart,
    };
    if (!body.symbol) return setError(t("position.errors.chooseCoin"));
    if (!body.buy_price || toNumber(body.buy_price) <= 0) return setError(t("position.errors.invalidPrice"));
    if (!body.quantity || toNumber(body.quantity) <= 0) return setError(t("position.errors.invalidQuantity"));
    if (body.fee_coin === null) return setError(t("position.errors.invalidFee"));
    if (toNumber(body.fee_coin) >= toNumber(body.quantity)) return setError(t("position.errors.feeTooHigh"));
    if ((targetPrice.trim() && !body.target_price) || (stopLoss.trim() && !body.stop_loss)) {
      return setError(t("position.errors.invalidTargets"));
    }

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
    <Modal title={editing ? t("position.editTitle", { symbol: position.symbol }) : t("position.newTitle")} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label={t("position.coin")} htmlFor="pf-symbol" hint={symbolLocked ? t("position.symbolLocked") : undefined}>
          <CoinPicker id="pf-symbol" value={symbol} onChange={setSymbol} disabled={symbolLocked} autoFocus={!editing && !defaultSymbol} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field
            label={t("position.buyPrice", { currency })}
            htmlFor="pf-price"
            hint={
              quote ? (
                <button type="button" className="text-neon-green hover:underline" onClick={() => setBuyPrice(quote.price)}>
                  {t("position.useCurrent", { price: fmtUnitPrice(quote.price) })}
                </button>
              ) : undefined
            }
          >
            <DecimalInput id="pf-price" value={buyPrice} onChange={setBuyPrice} placeholder="0.00" autoFocus={Boolean(defaultSymbol) && !editing} />
          </Field>
          <Field label={t("position.quantity")} htmlFor="pf-qty">
            <DecimalInput id="pf-qty" value={quantity} onChange={setQuantity} placeholder="0.0" />
          </Field>
          <Field
            label={t("position.fee", { symbol: symbol || t("position.feeCoinFallback") })}
            htmlFor="pf-fee"
            hint={t("position.feeHint")}
          >
            <DecimalInput id="pf-fee" value={fee} onChange={setFee} placeholder="0" />
          </Field>
          <Field label={t("position.date")} htmlFor="pf-date">
            <input id="pf-date" type="datetime-local" className="w-full" value={boughtAt}
              onChange={(e) => setBoughtAt(e.target.value)} required />
          </Field>
        </div>

        {/* Trade journal */}
        <Field label={t("position.journal.entryReason")} htmlFor="pf-reason">
          <textarea id="pf-reason" className="w-full" rows={3} maxLength={4000} value={entryReason}
            placeholder={t("position.journal.entryReasonPlaceholder")} onChange={(e) => setEntryReason(e.target.value)} />
        </Field>
        <Field label={t("position.journal.tags")} htmlFor="pf-tags" hint={t("position.journal.tagsHint")}>
          <input id="pf-tags" className="w-full uppercase placeholder:normal-case" value={tags}
            placeholder="RSI, SUPPORT, BB" onChange={(e) => setTags(e.target.value)} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t("position.journal.targetPrice", { currency })} htmlFor="pf-tp">
            <DecimalInput id="pf-tp" value={targetPrice} onChange={setTargetPrice} placeholder="—" />
          </Field>
          <Field label={t("position.journal.stopLoss", { currency })} htmlFor="pf-sl">
            <DecimalInput id="pf-sl" value={stopLoss} onChange={setStopLoss} placeholder="—" />
          </Field>
        </div>
        <Field label={t("position.journal.plan")} htmlFor="pf-plan">
          <textarea id="pf-plan" className="w-full" rows={2} maxLength={4000} value={plan} onChange={(e) => setPlan(e.target.value)} />
        </Field>
        <label className="flex items-center gap-2 text-sm text-zinc-400">
          <input type="checkbox" checked={showOnChart} onChange={(e) => setShowOnChart(e.target.checked)} />
          {t("chart.trades.showOnChart")}
        </label>

        <div className="grid grid-cols-3 gap-2 rounded-xl border border-white/[0.06] bg-ink-800/60 p-3 text-xs">
          <div>
            <div className="muted">{t("position.preview.cost")}</div>
            <div className="num text-sm text-zinc-200">{cost === null ? "—" : fmtMoney(cost)}</div>
          </div>
          <div>
            <div className="muted">{t("position.preview.held")}</div>
            <div className="num text-sm text-zinc-200">{held === null ? "—" : fmtQty(held)}</div>
          </div>
          <div className="text-right">
            <div className="muted">{t("position.preview.resultNow")}</div>
            <div className="text-sm">{value !== null && cost !== null ? <Pnl value={value - cost} /> : "—"}</div>
          </div>
        </div>

        {error && <p className="text-sm text-loss">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>{t("common.actions.cancel")}</button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? t("common.actions.saving") : editing ? t("common.actions.saveChanges") : t("position.submitNew")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
