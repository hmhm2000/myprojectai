import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { errorMessage } from "../api/client";
import { pricesApi } from "../api/endpoints";
import { PriceContext, useAuth } from "./contexts";

const CHECK_EVERY_MS = 15_000;

/**
 * Single source of prices for the whole app.
 * - Prices come from the backend (which keeps its own cache and decides whether to query exchanges).
 * - Switching views uses the data in memory, without new requests.
 * - When the tab is visible and the data is older than the TTL, it is fetched again from the backend.
 */
export function PriceProvider({ children }) {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const loadedAt = useRef(0);
  const ttlMs = (data?.ttl_seconds ?? 180) * 1000;

  const applyData = useCallback((prices) => {
    setData(prices);
    setError(null);
    loadedAt.current = Date.now();
    if (prices.force_available_in > 0) {
      setCooldownUntil(Date.now() + prices.force_available_in * 1000);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      applyData(await pricesApi.get());
    } catch (err) {
      setError(errorMessage(err, "prices.loadFailed"));
    }
  }, [applyData]);

  const forceRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      applyData(await pricesApi.refresh());
    } catch (err) {
      if (err.response?.status === 429) {
        setCooldownUntil(Date.now() + (err.response.data?.params?.retry_after ?? 5) * 1000);
      } else {
        setError(errorMessage(err, "prices.refreshFailed"));
      }
    } finally {
      setRefreshing(false);
    }
  }, [applyData]);

  useEffect(() => {
    if (!user) {
      setData(null);
      loadedAt.current = 0;
      return;
    }
    load();
  }, [user, load]);

  useEffect(() => {
    if (!user) return undefined;
    const id = setInterval(() => {
      if (document.visibilityState === "visible" && Date.now() - loadedAt.current >= ttlMs) load();
    }, CHECK_EVERY_MS);
    return () => clearInterval(id);
  }, [user, ttlMs, load]);

  // Changes only when the backend actually has new prices -> views can recalculate then.
  const version = data ? data.sources.map((s) => s.fetched_at).join("|") : "";

  const value = useMemo(
    () => ({
      data,
      prices: data?.prices ?? {},
      error,
      refreshing,
      cooldownUntil,
      version,
      forceRefresh,
      reload: load,
    }),
    [data, error, refreshing, cooldownUntil, version, forceRefresh, load],
  );

  return <PriceContext.Provider value={value}>{children}</PriceContext.Provider>;
}
