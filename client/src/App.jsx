import { lazy, Suspense, useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { AuthProvider } from "./context/AuthProvider";
import { useAuth } from "./context/contexts";
import { PriceProvider } from "./context/PriceProvider";
import AlertsPage from "./pages/AlertsPage";
import FavoritesPage from "./pages/FavoritesPage";
import JournalPage from "./pages/JournalPage";
import LoginPage from "./pages/LoginPage";
import PortfoliosPage from "./pages/PortfoliosPage";
import RegisterPage from "./pages/RegisterPage";
import SettingsPage from "./pages/SettingsPage";
import { LANGUAGE, t } from "./i18n";

// The chart library is large - load the chart page only when it is opened.
const ChartPage = lazy(() => import("./pages/ChartPage"));

function FullScreenLoader() {
  return (
    <div className="grid min-h-screen place-items-center text-sm text-zinc-500">
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 animate-ping rounded-full bg-neon-violet" />
        {t("common.loading")}
      </div>
    </div>
  );
}

function AppRoutes() {
  const { user, loading, registrationEnabled } = useAuth();
  if (loading) return <FullScreenLoader />;

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {registrationEnabled && <Route path="/register" element={<RegisterPage />} />}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/portfolios" element={<PortfoliosPage />} />
        <Route path="/journal" element={<JournalPage />} />
        <Route path="/chart" element={<Suspense fallback={<FullScreenLoader />}><ChartPage /></Suspense>} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/portfolios" replace />} />
    </Routes>
  );
}

export default function App() {
  useEffect(() => {
    document.title = t("common.app.name");
    document.documentElement.lang = LANGUAGE;
  }, []);

  return (
    <AuthProvider>
      <PriceProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </PriceProvider>
    </AuthProvider>
  );
}
