// Ceny: pasek stanu cen, przycisk odświeżania, giełdy.
export default {
  statusBar: {
    pricesFrom: "Ceny z {{time}}",
    noPrices: "Brak cen",
    loading: "Ładowanie cen…",
    refresh: "Odśwież ceny",
    refreshing: "Odświeżanie…",
    refreshWait: "Odśwież ({{seconds}}s)",
    refreshTitle: "Wymusza pobranie cen z giełd",
    staleSince: "ceny nieaktualne, ostatnie z {{date}}.",
    noData: "brak danych.",
  },
  // Nazwy giełd (źródeł cen).
  sources: {
    okx: "OKX",
    bybit: "Bybit",
  },
  // Błędy giełd - klucze to kody z backendu (sources[].error_code).
  sourceErrors: {
    connection_error: "brak połączenia z giełdą",
    rate_limited: "przekroczony limit zapytań",
    http_error: "giełda zwróciła błąd",
    api_error: "błąd API giełdy",
    invalid_response: "niepoprawna odpowiedź giełdy",
    unexpected_error: "nieoczekiwany błąd",
  },
  loadFailed: "Nie udało się pobrać cen z serwera",
  refreshFailed: "Nie udało się odświeżyć cen",
  change24h: "24h",
};
