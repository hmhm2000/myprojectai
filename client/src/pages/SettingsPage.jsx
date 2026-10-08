import { useEffect, useState } from "react";
import { API_URL, errorMessage } from "../api/client";
import { usersApi } from "../api/endpoints";
import ManualCleanup from "../components/ManualCleanup";
import PriceStatusBar from "../components/PriceStatusBar";
import { ErrorBanner } from "../components/ui";
import { useAuth, usePrices } from "../context/contexts";
import { t } from "../i18n";
import Trans from "../i18n/Trans";
import { fmtDateTime } from "../lib/format";
import { sourceName } from "../lib/sources";


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
        <p className="text-sm text-zinc-500">{t("common.loading")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-sm">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-zinc-500">
                <th className="pb-2 font-medium">{t("settings.users.username")}</th>
                <th className="pb-2 font-medium">{t("settings.users.email")}</th>
                <th className="pb-2 font-medium">{t("settings.users.role")}</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-white/[0.04]">
                  <td className="py-2 text-zinc-200">{u.username}</td>
                  <td className="py-2 text-zinc-400">{u.email}</td>
                  <td className="py-2">{u.is_admin ? <span className="chip text-neon-violet">{t("settings.account.roleAdmin")}</span> : <span className="chip">{t("settings.account.roleUser")}</span>}</td>
                  <td className="py-2 text-right">
                    {u.id !== currentUserId && (
                      <button type="button" className="btn-ghost py-1 text-xs" onClick={() => toggle(u.id)}>
                        {u.is_admin ? t("settings.users.revokeAdmin") : t("settings.users.grantAdmin")}
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
      <Section title={t("settings.prices.title")}>
        <div className="mb-4">
          <PriceStatusBar />
        </div>
        {data && (
          <>
            <Row label={t("settings.prices.quoteCurrency")}>{data.quote_currency}</Row>
            <Row label={t("settings.prices.ttl")}>{t("settings.prices.ttlValue", { minutes: Math.round((data.ttl_seconds / 60) * 10) / 10 })}</Row>
            <Row label={t("settings.prices.coinsAvailable")}>{Object.keys(data.prices).length}</Row>
            {data.sources.map((s) => (
              <Row key={s.name} label={sourceName(s.name)}>
                <span className={s.ok && !s.stale ? "text-profit" : "text-amber-300"}>
                  {s.ok && !s.stale ? t("settings.prices.ok") : t("settings.prices.stale")}
                </span>
                <span className="text-zinc-500"> · {t("settings.prices.pairs", { count: s.count })} · {fmtDateTime(s.fetched_at)}</span>
              </Row>
            ))}
          </>
        )}
        <p className="mt-4 text-xs text-zinc-500">
          <Trans
            k="settings.prices.hint"
            values={{
              file: <code className="text-zinc-300">server/.env</code>,
              keys: <code>PRICE_TTL_SECONDS, PRICE_FORCE_MIN_INTERVAL_SECONDS, QUOTE_CURRENCY</code>,
            }}
          />
        </p>
      </Section>

      <Section title={t("settings.account.title")}>
        <Row label={t("settings.account.username")}>{user.username}</Row>
        <Row label={t("settings.account.email")}>{user.email}</Row>
        <Row label={t("settings.account.role")}>{user.is_admin ? t("settings.account.roleAdmin") : t("settings.account.roleUser")}</Row>
        <Row label={t("settings.account.registration")}>{registrationEnabled ? t("settings.account.enabled") : t("settings.account.disabled")}</Row>
        <Row label={t("settings.account.apiServer")}><span className="num text-xs">{API_URL}</span></Row>
        <p className="mt-4 text-xs text-zinc-500">
          <Trans
            k="settings.account.registrationHint"
            values={{ file: <code className="text-zinc-300">server/.env</code>, setting: <code>ALLOW_REGISTRATION=true</code> }}
          />
        </p>
        <button type="button" className="btn-ghost mt-4" onClick={logout}>{t("nav.logout")}</button>
      </Section>

      <div className="lg:col-span-2">
        <Section title={t("settings.cleanup.title")}>
          <ManualCleanup />
        </Section>
      </div>

      {user.is_admin && (
        <div className="lg:col-span-2">
          <Section title={t("settings.users.title")}>
            <UsersAdmin currentUserId={user.id} />
          </Section>
        </div>
      )}
    </div>
  );
}
