import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/contexts";
import AuthCard from "./AuthCard";

export default function RegisterPage() {
  const { register } = useAuth();
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const update = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(form.username.trim(), form.email.trim(), form.password);
    } catch (err) {
      setError(errorMessage(err, "Rejestracja nie powiodła się"));
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Rejestracja"
      footer={
        <>
          Masz już konto?{" "}
          <Link to="/login" className="text-neon-green hover:underline">
            Zaloguj się
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="r-username">Nazwa użytkownika</label>
          <input id="r-username" name="username" className="w-full" value={form.username} onChange={update}
            minLength={3} maxLength={50} autoComplete="username" required />
        </div>
        <div>
          <label className="label" htmlFor="r-email">E-mail</label>
          <input id="r-email" name="email" type="email" className="w-full" value={form.email} onChange={update}
            autoComplete="email" required />
        </div>
        <div>
          <label className="label" htmlFor="r-password">Hasło (min. 8 znaków)</label>
          <input id="r-password" name="password" type="password" className="w-full" value={form.password}
            onChange={update} minLength={8} autoComplete="new-password" required />
        </div>
        {error && <p className="text-sm text-loss">{error}</p>}
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? "Tworzenie konta…" : "Załóż konto"}
        </button>
      </form>
    </AuthCard>
  );
}
