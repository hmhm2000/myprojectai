import { useCallback, useEffect, useMemo, useState } from "react";
import { tokenStore } from "../api/client";
import { authApi } from "../api/endpoints";
import { AuthContext } from "./contexts";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [registrationEnabled, setRegistrationEnabled] = useState(false);

  useEffect(() => {
    authApi
      .config()
      .then((config) => setRegistrationEnabled(config.registration_enabled))
      .catch(() => setRegistrationEnabled(false));

    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  // Interceptor axiosa zgłasza wygaśnięcie tokenu.
  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("auth:logout", onLogout);
    return () => window.removeEventListener("auth:logout", onLogout);
  }, []);

  const login = useCallback(async (username, password) => {
    const { access_token } = await authApi.login(username, password);
    tokenStore.set(access_token);
    setUser(await authApi.me());
  }, []);

  const register = useCallback(async (username, email, password) => {
    const { access_token } = await authApi.register(username, email, password);
    tokenStore.set(access_token);
    setUser(await authApi.me());
  }, []);

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, registrationEnabled, login, register, logout }),
    [user, loading, registrationEnabled, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
