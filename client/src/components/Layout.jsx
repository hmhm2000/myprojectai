import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/contexts";
import { t } from "../i18n";
import { LogoutIcon, SettingsIcon, StarIcon, WalletIcon } from "./icons";

const LINKS = [
  { to: "/portfolios", labelKey: "nav.portfolios", Icon: WalletIcon },
  { to: "/favorites", labelKey: "nav.favorites", Icon: StarIcon },
  { to: "/settings", labelKey: "nav.settings", Icon: SettingsIcon },
];

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="relative grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-neon-violet to-neon-green text-ink-950 shadow-neon-violet">
        <WalletIcon size={16} />
      </div>
      <span className="text-sm font-semibold tracking-wide text-zinc-100">
        {t("common.app.logoMain")}<span className="text-neon-green">{t("common.app.logoAccent")}</span>
      </span>
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen pb-20 md:pb-0">
      {/* Top bar */}
      <header className="sticky top-0 z-40 border-b border-white/[0.06] bg-ink-950/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
          <Logo />
          <nav className="hidden items-center gap-1 md:flex">
            {LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition ${
                    isActive
                      ? "bg-white/[0.06] text-zinc-100 shadow-[inset_0_-2px_0_0_theme(colors.neon.violet)]"
                      : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                  }`
                }
              >
                <link.Icon size={16} />
                {t(link.labelKey)}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <span className="hidden text-xs text-zinc-500 sm:inline">{user?.username}</span>
            <button type="button" className="btn-icon" onClick={logout} title={t("nav.logout")} aria-label={t("nav.logout")}>
              <LogoutIcon size={16} />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6 animate-fade-in">
        <Outlet />
      </main>

      {/* Bottom navigation on phones */}
      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-white/[0.06] bg-ink-950/90 backdrop-blur-md md:hidden">
        <div className="grid grid-cols-3">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 py-2.5 text-[11px] transition ${
                  isActive ? "text-neon-green" : "text-zinc-500"
                }`
              }
            >
              <link.Icon size={20} />
              {t(link.labelKey)}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}

export { Logo };
