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

export const indicatorsApi = {
  list: () => data(api.get("/api/indicators")),
  values: (id, { symbol, interval, start, end, params }) =>
    data(api.get(`/api/indicators/${id}/values`, { params: { symbol, interval, start, end, params: JSON.stringify(params) } })),
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
