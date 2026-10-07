import axios from "axios";

export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";

const TOKEN_KEY = "token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export const api = axios.create({ baseURL: API_URL, timeout: 20000 });

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    // Wygasły lub nieprawidłowy token -> wylogowanie.
    if (error.response?.status === 401 && tokenStore.get()) {
      tokenStore.clear();
      window.dispatchEvent(new Event("auth:logout"));
    }
    return Promise.reject(error);
  },
);

/** Czytelny komunikat błędu z odpowiedzi FastAPI. */
export function errorMessage(error, fallback = "Coś poszło nie tak") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (d.msg || "").replace(/^Value error, /, ""))
      .filter(Boolean)
      .join("; ");
  }
  if (error?.code === "ERR_NETWORK") return "Brak połączenia z serwerem";
  return fallback;
}
