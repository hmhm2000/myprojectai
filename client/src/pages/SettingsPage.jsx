import { useEffect, useState } from "react";
import { API_URL, errorMessage } from "../api/client";
import { usersApi } from "../api/endpoints";
import PriceStatusBar from "../components/PriceStatusBar";
import { ErrorBanner } from "../components/ui";
import { useAuth, usePrices } from "../context/contexts";
import { fmtDateTime } from "../lib/format";

const SOURCE_NAMES = { okx: "OKX", bybit: "Bybit" };

function Section({ title, children }) {
  return (
    <section className="tile glow p-5">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-zinc-400">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, children }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-white/[0.04] py-2 text-sm last:border-0">
      <span className="text-zinc-500">{label}</span>
      <span className="text-zinc-200">{children}</span>
    </div>
  );
}

function UsersAdmin({ currentUserId }) {
  const [users, setUsers] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    usersApi.list().then(setUsers).catch((err) => setError(errorMessage(err)));
  }, []);

  const toggle = async (id) => {
    try {
      const updated = await usersApi.toggleAdmin(id);
      setUsers((list) => list.map((u) => (u.id === id ? updated : u)));
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <div className="space-y-3">
      <ErrorBanner onClose={() => setError(null)}>{error}</ErrorBanner>
      {users === null ? (
        <p className="text-sm text-zinc-500">Ładowanie…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-sm">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-zinc-500">
                <th className="pb-2 font-medium">Użytkownik</th>
                <th className="pb-2 font-medium">E-mail</th>
                <th className="pb-2 font-medium">Rola</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-white/[0.04]">
                  <td className="py-2 text-zinc-200">{u.username}</td>
                  <td className="py-2 text-zinc-400">{u.email}</td>
                  <td className="py-2">{u.is_admin ? <span className="chip text-neon-violet">admin</span> : <span className="chip">użytkownik</span>}</td>
                  <td className="py-2 text-right">
                    {u.id !== currentUserId && (
                      <button type="button" className="btn-ghost py-1 text-xs" onClick={() => toggle(u.id)}>
                        {u.is_admin ? "Odbierz admina" : "Nadaj admina"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { user, registrationEnabled, logout } = useAuth();
  const { data } = usePrices();

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Section title="Ceny">
        <div className="mb-4">
          <PriceStatusBar />
        </div>
        {data && (
          <>
            <Row label="Waluta kwotowania">{data.quote_currency}</Row>
            <Row label="Cache (TTL)">{Math.round(data.ttl_seconds / 60 * 10) / 10} min</Row>
            <Row label="Dostępnych coinów">{Object.keys(data.prices).length}</Row>
            {data.sources.map((s) => (
              <Row key={s.name} label={SOURCE_NAMES[s.name] ?? s.name}>
                <span className={s.ok && !s.stale ? "text-profit" : "text-amber-300"}>
                  {s.ok && !s.stale ? "OK" : "nieaktualne"}
                </span>
                <span className="text-zinc-500"> · {s.count} par · {fmtDateTime(s.fetched_at)}</span>
              </Row>
            ))}
          </>
        )}
        <p className="mt-4 text-xs text-zinc-500">
          TTL, limit odświeżania i walutę zmienisz w <code className="text-zinc-300">server/.env</code>
          {" "}(<code>PRICE_TTL_SECONDS</code>, <code>PRICE_FORCE_MIN_INTERVAL_SECONDS</code>, <code>QUOTE_CURRENCY</code>).
        </p>
      </Section>

      <Section title="Konto">
        <Row label="Użytkownik">{user.username}</Row>
        <Row label="E-mail">{user.email}</Row>
        <Row label="Rola">{user.is_admin ? "admin" : "użytkownik"}</Row>
        <Row label="Rejestracja nowych kont">{registrationEnabled ? "włączona" : "wyłączona"}</Row>
        <Row label="Serwer API"><span className="num text-xs">{API_URL}</span></Row>
        <p className="mt-4 text-xs text-zinc-500">
          Rejestrację włączysz w <code className="text-zinc-300">server/.env</code>: <code>ALLOW_REGISTRATION=true</code>.
        </p>
        <button type="button" className="btn-ghost mt-4" onClick={logout}>Wyloguj</button>
      </Section>

      {user.is_admin && (
        <div className="lg:col-span-2">
          <Section title="Użytkownicy">
            <UsersAdmin currentUserId={user.id} />
          </Section>
        </div>
      )}
    </div>
  );
}
