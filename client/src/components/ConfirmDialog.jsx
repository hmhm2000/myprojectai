import { useState } from "react";
import { errorMessage } from "../api/client";
import Modal from "./Modal";

/** Potwierdzenie operacji nieodwracalnej (np. usunięcie portfela). */
export default function ConfirmDialog({ title, message, confirmLabel = "Usuń", onConfirm, onClose }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Modal
      title={title}
      onClose={busy ? () => {} : onClose}
      footer={
        <>
          <button type="button" className="btn-ghost" onClick={onClose} disabled={busy}>
            Anuluj
          </button>
          <button type="button" className="btn-danger" onClick={confirm} disabled={busy} autoFocus>
            {busy ? "Usuwanie…" : confirmLabel}
          </button>
        </>
      }
    >
      <div className="space-y-3 text-sm text-zinc-300">{message}</div>
      {error && <p className="mt-3 text-sm text-loss">{error}</p>}
    </Modal>
  );
}
