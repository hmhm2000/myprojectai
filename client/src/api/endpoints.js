import { api } from "./client";

const data = (promise) => promise.then((response) => response.data);

export const authApi = {
  config: () => data(api.get("/api/auth/config")),
  me: () => data(api.get("/api/auth/me")),
  login: (username, password) =>
    data(
      api.post("/api/auth/login", new URLSearchParams({ username, password }), {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      }),
    ),
  register: (username, email, password) => data(api.post("/api/auth/register", { username, email, password })),
};

export const usersApi = {
  list: () => data(api.get("/api/users/")),
  toggleAdmin: (id) => data(api.put(`/api/users/${id}/toggle-admin`)),
};

export const pricesApi = {
  get: () => data(api.get("/api/prices")),
  refresh: () => data(api.post("/api/prices/refresh")),
};

export const portfoliosApi = {
  list: () => data(api.get("/api/portfolios")),
  get: (id) => data(api.get(`/api/portfolios/${id}`)),
  create: (name) => data(api.post("/api/portfolios", { name })),
  rename: (id, name) => data(api.patch(`/api/portfolios/${id}`, { name })),
  remove: (id) => api.delete(`/api/portfolios/${id}`),

  addPosition: (portfolioId, body) => data(api.post(`/api/portfolios/${portfolioId}/positions`, body)),
  updatePosition: (id, body) => data(api.put(`/api/positions/${id}`, body)),
  removePosition: (id) => data(api.delete(`/api/positions/${id}`)),
  positionTiming: (id) => data(api.get(`/api/positions/${id}/timing`)),
  setPositionOnChart: (id, show) => data(api.patch(`/api/positions/${id}/chart`, { show_on_chart: show })),
  setSaleOnChart: (groupId, show) => data(api.patch(`/api/sale-groups/${groupId}/chart`, { show_on_chart: show })),

  reorderPositions: (portfolioId, positionIds) =>
    data(api.put(`/api/portfolios/${portfolioId}/positions/order`, { position_ids: positionIds })),

  // A sale = group: price, date, total fee + split across positions (allocations).
  addSale: (portfolioId, body) => data(api.post(`/api/portfolios/${portfolioId}/sales`, body)),
  updateSale: (groupId, body) => data(api.put(`/api/sale-groups/${groupId}`, body)),
  removeSale: (groupId) => data(api.delete(`/api/sale-groups/${groupId}`)),
};

export const candlesApi = {
  get: (symbol, interval, { limit = 500, before = null } = {}) =>
    data(api.get("/api/candles", { params: { symbol, interval, limit, ...(before ? { before } : {}) } })),
};

export const alertsApi = {
  list: () => data(api.get("/api/alerts")),
  create: (body) => data(api.post("/api/alerts", body)),
  update: (id, body) => data(api.patch(`/api/alerts/${id}`, body)),
  remove: (id) => api.delete(`/api/alerts/${id}`),
  check: (id) => data(api.get(`/api/alerts/${id}/check`)),
  events: ({ unseenOnly = false } = {}) => data(api.get("/api/alerts/events", { params: { unseen_only: unseenOnly } })),
  markSeen: (ids = null) => api.post("/api/alerts/events/seen", ids ? { ids } : {}),
};

export const indicatorsApi = {
  list: () => data(api.get("/api/indicators")),
  values: (id, { symbol, interval, start, end, params, indicatorInterval = null }) =>
    data(api.get(`/api/indicators/${id}/values`, {
      params: { symbol, interval, start, end, params: JSON.stringify(params), ...(indicatorInterval ? { indicator_interval: indicatorInterval } : {}) },
    })),
};

// The user's chart indicators (saved on the server, per user).
export const chartIndicatorsApi = {
  list: () => data(api.get("/api/chart-indicators")),
  add: (body) => data(api.post("/api/chart-indicators", body)),
  update: (id, body) => data(api.put(`/api/chart-indicators/${id}`, body)),
  reset: (id) => data(api.post(`/api/chart-indicators/${id}/reset`)),
  remove: (id) => api.delete(`/api/chart-indicators/${id}`),
};

export const chartIntervalsApi = {
  list: () => data(api.get("/api/chart-intervals")),
  add: (name) => data(api.post("/api/chart-intervals", { name })),
  setPinned: (name, pinned) => data(api.put(`/api/chart-intervals/${encodeURIComponent(name)}`, { pinned })),
  remove: (name) => api.delete(`/api/chart-intervals/${encodeURIComponent(name)}`),
};

export const importApi = {
  status: () => data(api.get("/api/import")),
  sync: () => data(api.post("/api/import/sync")),
  keep: (kind, id) => data(api.post("/api/import/missing/keep", { kind, id: String(id) })),
  remove: (kind, id) => data(api.post("/api/import/missing/delete", { kind, id: String(id) })),
};

export const transactionsApi = {
  list: (portfolioId) => data(api.get(`/api/portfolios/${portfolioId}/transactions`)),
  summary: (portfolioId, params) => data(api.get(`/api/portfolios/${portfolioId}/cost-summary`, { params })),
  update: (kind, id, body) => api.patch(`/api/transactions/${kind}/${encodeURIComponent(id)}`, body),
  setMethod: (portfolioId, method) => api.put(`/api/portfolios/${portfolioId}/cost-method`, { cost_method: method }),
};

export const journalApi = {
  stats: (portfolioId = null) => data(api.get("/api/journal/stats", { params: portfolioId ? { portfolio_id: portfolioId } : {} })),
};

export const favoritesApi = {
  list: () => data(api.get("/api/favorite-lists")),
  create: (name) => data(api.post("/api/favorite-lists", { name })),
  rename: (id, name) => data(api.patch(`/api/favorite-lists/${id}`, { name })),
  remove: (id) => api.delete(`/api/favorite-lists/${id}`),
  addCoin: (id, symbol) => data(api.post(`/api/favorite-lists/${id}/coins`, { symbol })),
  removeCoin: (id, symbol) => data(api.delete(`/api/favorite-lists/${id}/coins/${encodeURIComponent(symbol)}`)),
};
