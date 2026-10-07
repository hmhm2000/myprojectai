import { useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../context/contexts";
import { t } from "../i18n";
import AuthCard from "./AuthCard";

export default function LoginPage() {
  const { login, registrationEnabled } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(errorMessage(err, "auth.login.failed"));
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title={t("auth.login.title")}
      footer={
        registrationEnabled && (
          <>
            {t("auth.login.noAccount")}{" "}
            <Link to="/register" className="text-neon-green hover:underline">
              {t("auth.login.registerLink")}
            </Link>
          </>
        )
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="username">{t("auth.login.username")}</label>
          <input id="username" className="w-full" value={username} onChange={(e) => setUsername(e.target.value)}
            autoComplete="username" autoFocus required />
        </div>
        <div>
          <label className="label" htmlFor="password">{t("auth.login.password")}</label>
          <input id="password" type="password" className="w-full" value={password}
            onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </div>
        {error && <p className="text-sm text-loss">{error}</p>}
        <button type="submit" className="btn-primary w-full" disabled={busy}>
          {busy ? t("auth.login.submitting") : t("auth.login.submit")}
        </button>
      </form>
    </AuthCard>
  );
}
