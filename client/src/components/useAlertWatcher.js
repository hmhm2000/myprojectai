import { useEffect, useState } from "react";
import { alertsApi, indicatorsApi } from "../api/endpoints";
import { t } from "../i18n";
import { conditionText } from "../lib/alertText";

const POLL_MS = 60_000;
const NOTIFIED_KEY = "alerts:lastNotifiedId";

const readLastNotified = () => {
  try {
    return Number(localStorage.getItem(NOTIFIED_KEY)) || 0;
  } catch {
    return 0;
  }
};

/**
 * Polls unseen alert events once a minute (only while logged in) and shows a browser notification
 * for every new one. Returns the number of unseen events (badge in the menu).
 * The Alerts page dispatches "alerts:changed" after marking events as seen.
 */
export function useAlertWatcher(enabled) {
  const [unseen, setUnseen] = useState(0);

  useEffect(() => {
    if (!enabled) return undefined;
    let definitions = null;
    let cancelled = false;

    const poll = async () => {
      try {
        const events = await alertsApi.events({ unseenOnly: true });
        if (cancelled) return;
        setUnseen(events.length);
        const lastNotified = readLastNotified();
        const fresh = events.filter((e) => e.id > lastNotified);
        if (!fresh.length) return;
        localStorage.setItem(NOTIFIED_KEY, String(Math.max(...fresh.map((e) => e.id))));
        if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
        definitions ??= await indicatorsApi.list().catch(() => []);
        for (const event of fresh.slice(0, 5)) {
          new Notification(t("alerts.notification.title", { symbol: event.symbol }), {
            body: t("alerts.notification.body", { condition: conditionText(event.condition, definitions), interval: event.interval }),
            tag: `alert-${event.id}`,
          });
        }
      } catch {
        // offline / logged out - try again on the next tick
      }
    };

    poll();
    const id = setInterval(poll, POLL_MS);
    window.addEventListener("alerts:changed", poll);
    return () => {
      cancelled = true;
      clearInterval(id);
      window.removeEventListener("alerts:changed", poll);
    };
  }, [enabled]);

  return unseen;
}
