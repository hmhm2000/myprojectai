import { hasTranslation, t } from "../i18n";

/** Display name of a price source (exchange), e.g. "okx" -> "OKX". */
export const sourceName = (name) => (hasTranslation(`prices.sources.${name}`) ? t(`prices.sources.${name}`) : name);

/** Translated description of an exchange error code from /api/prices (sources[].error_code). */
export const sourceErrorText = (code) =>
  hasTranslation(`prices.sourceErrors.${code}`) ? t(`prices.sourceErrors.${code}`) : code;
