import { useState } from "react";
import { errorMessage } from "../api/client";
import Modal from "./Modal";
import { Field } from "./ui";

/** Okno z jednym polem "nazwa" (nowy/zmiana nazwy portfela lub listy). */
export default function NameDialog({ title, label = "Nazwa", initial = "", submitLabel = "Zapisz", onSubmit, onClose }) {
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
          <button type="button" className="btn-ghost" onClick={onClose}>Anuluj</button>
          <button type="submit" className="btn-primary" disabled={busy || !name.trim()}>
            {busy ? "Zapisywanie…" : submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}
