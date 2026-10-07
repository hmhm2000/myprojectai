import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { AuthProvider } from "./context/AuthProvider";
import { useAuth } from "./context/contexts";
import { PriceProvider } from "./context/PriceProvider";
import FavoritesPage from "./pages/FavoritesPage";
import LoginPage from "./pages/LoginPage";
import PortfoliosPage from "./pages/PortfoliosPage";
import RegisterPage from "./pages/RegisterPage";
import SettingsPage from "./pages/SettingsPage";

function FullScreenLoader() {
  return (
    <div className="grid min-h-screen place-items-center text-sm text-zinc-500">
      <div className="flex items-center gap-3">
        <span className="h-2 w-2 animate-ping rounded-full bg-neon-violet" />
        Ładowanie…
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
        <Route path="/favorites" element={<FavoritesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/portfolios" replace />} />
    </Routes>
  );
}

export default function App() {
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
