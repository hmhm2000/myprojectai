import axios from "axios";
import { hasTranslation, t } from "../i18n";
import { fmtDate, fmtQty } from "../lib/format";

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
    // Expired or invalid token -> log out.
    if (error.response?.status === 401 && tokenStore.get()) {
      tokenStore.clear();
      window.dispatchEvent(new Event("auth:logout"));
    }
    return Promise.reject(error);
  },
);

// Error params that need locale formatting before being inserted into a message.
const PARAM_FORMATTERS = {
  date: fmtDate,
  max: fmtQty,
  sold: fmtQty,
};

function formatParams(params = {}) {
  return Object.fromEntries(
    Object.entries(params).map(([name, value]) => [name, PARAM_FORMATTERS[name] ? PARAM_FORMATTERS[name](value) : value]),
  );
}

/**
 * Human-readable, translated message for an API error.
 * The backend sends a stable `code` (+ `params`) that maps to errors.api.<code> in the locale files;
 * validation errors (422) map their `type` to errors.validation.<type>.
 */
export function errorMessage(error, fallbackKey = "errors.generic") {
  const data = error?.response?.data;
  if (data?.code && hasTranslation(`errors.api.${data.code}`)) {
    return t(`errors.api.${data.code}`, formatParams(data.params));
  }
  if (Array.isArray(data?.detail)) {
    const messages = data.detail.map((item) =>
      hasTranslation(`errors.validation.${item.type}`) ? t(`errors.validation.${item.type}`) : t("errors.validation.default"),
    );
    return [...new Set(messages)].join("; ");
  }
  if (error?.code === "ERR_NETWORK") return t("errors.network");
  return t(fallbackKey);
}
