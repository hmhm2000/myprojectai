import { useEffect, useState } from "react";
import { myCoinsApi } from "../api/endpoints";

// The user's coins for the coin search (favorites + held), shared by every CoinPicker.
const EMPTY = { favorites: [], held: [] };
const MAX_AGE_MS = 60_000;
let cache = null;
let loadedAt = 0;
let loading = null;
const listeners = new Set();

function load() {
  if (!loading) {
    loading = myCoinsApi.get()
      .then((data) => {
        cache = data;
        loadedAt = Date.now();
        listeners.forEach((fn) => fn(data));
      })
      .catch(() => {})
      .finally(() => {
        loading = null;
      });
  }
  return loading;
}

/** { favorites: [...], held: [...] } - refreshed after changes of portfolios / favorites. */
export function useMyCoins() {
  const [coins, setCoins] = useState(cache ?? EMPTY);
  useEffect(() => {
    listeners.add(setCoins);
    if (!cache || Date.now() - loadedAt > MAX_AGE_MS) load();
    const refresh = () => load();
    window.addEventListener("portfolios:changed", refresh);
    window.addEventListener("favorites:changed", refresh);
    return () => {
      listeners.delete(setCoins);
      window.removeEventListener("portfolios:changed", refresh);
      window.removeEventListener("favorites:changed", refresh);
    };
  }, []);
  return coins;
}
