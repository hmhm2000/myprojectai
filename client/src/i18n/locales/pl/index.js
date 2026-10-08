// Polski. Każdy plik to jeden obszar aplikacji - klucz "portfolio.summary.value"
// oznacza plik portfolio.js -> summary -> value.
//
// Zasady:
// - {{nazwa}} to miejsce na wartość wstawianą przez kod (nie tłumaczyć nazwy w nawiasach).
// - Obiekty { one, few, many, other } to formy liczby mnogiej (1 pozycja, 2 pozycje, 5 pozycji).
import alerts from "./alerts.js";
import auth from "./auth.js";
import chart from "./chart.js";
import coins from "./coins.js";
import common from "./common.js";
import errors from "./errors.js";
import favorites from "./favorites.js";
import imports from "./imports.js";
import journal from "./journal.js";
import nav from "./nav.js";
import portfolio from "./portfolio.js";
import position from "./position.js";
import prices from "./prices.js";
import sale from "./sale.js";
import settings from "./settings.js";
import transactions from "./transactions.js";

export default {
  meta: {
    language: "pl",
    localeTag: "pl-PL", // format liczb i dat
    currencySymbol: "$", // symbol przed kwotami w walucie kwotowania (USDT)
  },
  alerts,
  auth,
  chart,
  coins,
  common,
  errors,
  favorites,
  imports,
  journal,
  nav,
  portfolio,
  position,
  prices,
  sale,
  transactions,
  settings,
};
