// Translations.
//
// All user-facing texts live in src/i18n/locales/<language>/*.js - never hard-code them in components.
// Usage:  t("portfolio.summary.value")
//         t("portfolio.dialogs.deleteSaleShared", { count: 3 })  -> plural form picked automatically
//         t("errors.api.sale.exceeds_available", { max: "0,5", symbol: "BTC" })  -> {{max}}, {{symbol}}
//
// Language is chosen at build/start time with VITE_LANGUAGE in client/.env (default: "pl").
// Adding a language: copy locales/pl to locales/<code>, translate the values and register it below.
import pl from "./locales/pl";

const LOCALES = { pl };
const DEFAULT_LANGUAGE = "pl";

export const LANGUAGE = LOCALES[import.meta.env.VITE_LANGUAGE] ? import.meta.env.VITE_LANGUAGE : DEFAULT_LANGUAGE;

const messages = LOCALES[LANGUAGE];

/** BCP 47 tag used for number/date formatting (e.g. "pl-PL"). */
export const LOCALE_TAG = messages.meta.localeTag;
/** Symbol shown in front of amounts in the quote currency. */
export const CURRENCY_SYMBOL = messages.meta.currencySymbol;

const pluralRules = new Intl.PluralRules(LOCALE_TAG);

function lookup(key) {
  return key.split(".").reduce((node, part) => (node == null ? undefined : node[part]), messages);
}

/** True when a translation exists for the key (used to translate backend error codes). */
export function hasTranslation(key) {
  const value = lookup(key);
  return typeof value === "string" || (value != null && typeof value === "object" && "other" in value);
}

/**
 * Translated text for a key. Plural keys are objects like { one, few, many, other }
 * (forms from Intl.PluralRules) and need a numeric `count` param.
 */
export function t(key, params = {}) {
  let value = lookup(key);
  if (value != null && typeof value === "object" && "other" in value) {
    value = value[pluralRules.select(Number(params.count ?? 0))] ?? value.other;
  }
  if (typeof value !== "string") {
    if (import.meta.env.DEV) console.warn(`[i18n] Missing translation: ${key}`);
    return key;
  }
  return value.replace(/\{\{(\w+)\}\}/g, (match, name) => (params[name] ?? match).toString());
}
