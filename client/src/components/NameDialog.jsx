import { useState } from "react";
import { errorMessage } from "../api/client";
import { t } from "../i18n";
import Modal from "./Modal";
import { Field } from "./ui";

/** Dialog with a single "name" field (create/rename a portfolio or list). */
export default function NameDialog({ title, label = t("common.name"), initial = "", submitLabel = t("common.actions.save"), onSubmit, onClose }) {
  const [name, setName] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(name.trim());
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label={label} htmlFor="name-input">
          <input id="name-input" className="w-full" value={name} onChange={(e) => setName(e.target.value)}
            maxLength={60} autoFocus required />
        </Field>
        {error && <p className="text-sm text-loss">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-ghost" onClick={onClose}>{t("common.actions.cancel")}</button>
          <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
            {busy ? t("common.actions.saving") : submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}
