import { useEffect, useState } from "react";
import { chartIntervalsApi } from "../api/endpoints";
import { takeLegacyCustomIntervals } from "./intervals";

// The user's intervals (saved on the server), shared by the chart, the indicator modal and alerts.
let cache = null;
let loading = null;
const listeners = new Set();

function publish(list) {
  cache = list;
  listeners.forEach((fn) => fn(list));
  return list;
}

async function load() {
  // Custom intervals from the old browser-only version go to the server once.
  for (const name of takeLegacyCustomIntervals()) await chartIntervalsApi.add(name).catch(() => {});
  return publish(await chartIntervalsApi.list());
}

/** [intervals, actions]: intervals = [{ name, custom, pinned }] (null while loading). */
export function useChartIntervals() {
  const [list, setList] = useState(cache);

  useEffect(() => {
    listeners.add(setList);
    if (!cache && !loading) loading = load().catch(() => null).finally(() => { loading = null; });
    return () => listeners.delete(setList);
  }, []);

  const actions = {
    add: async (name) => publish(await chartIntervalsApi.add(name)),
    setPinned: async (name, pinned) => {
      const before = cache;
      publish(cache.map((i) => (i.name === name ? { ...i, pinned } : i)));   // instant, server confirms
      try {
        return publish(await chartIntervalsApi.setPinned(name, pinned));
      } catch (err) {
        publish(before);
        throw err;
      }
    },
    remove: async (name) => {
      await chartIntervalsApi.remove(name);
      return publish(cache.filter((i) => i.name !== name));
    },
  };
  return [list, actions];
}
