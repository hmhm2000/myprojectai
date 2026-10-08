// Komunikaty błędów.
// "api" - klucze to kody błędów z backendu (pole "code" w odpowiedzi, np. "sale.exceeds_available").
// "validation" - klucze to typy błędów walidacji (pole "type" w odpowiedzi 422).
export default {
  generic: "Coś poszło nie tak",
  network: "Brak połączenia z serwerem",

  api: {
    auth: {
      invalid_token: "Sesja wygasła - zaloguj się ponownie",
      admin_required: "Brak uprawnień administratora",
      registration_disabled: "Rejestracja jest wyłączona",
      user_exists: "Użytkownik lub e-mail już istnieje",
      invalid_credentials: "Nieprawidłowa nazwa użytkownika lub hasło",
    },
    users: {
      cannot_change_own_role: "Nie możesz zmienić własnej roli",
      not_found: "Użytkownik nie istnieje",
    },
    portfolio: {
      not_found: "Portfel nie istnieje",
    },
    position: {
      not_found: "Pozycja nie istnieje",
      invalid_order: "Nieprawidłowa kolejność pozycji",
      symbol_locked: "Nie można zmienić coina pozycji, która ma sprzedaże",
      quantity_below_sold: "Ilość po opłacie nie może być mniejsza niż już sprzedana ({{sold}} {{symbol}})",
    },
    import: {
      entry_not_found: "Wpis nie istnieje",
      entry_not_flagged: "Ten wpis nie jest oznaczony jako nieobecny w eksporcie",
      invalid_method: "Nieznana metoda kosztu: {{method}}",
    },
    sale: {
      not_found: "Sprzedaż nie istnieje",
      position_not_in_portfolio: "Pozycja nie należy do tego portfela",
      mixed_coins: "Jedna sprzedaż może obejmować pozycje tylko jednego coina",
      exceeds_available: "Pozycja z {{date}}: można sprzedać najwyżej {{max}} {{symbol}}",
    },
    favorites: {
      list_not_found: "Lista nie istnieje",
      coin_exists: "{{symbol}} już jest na tej liście",
      coin_not_found: "Tego coina nie ma na liście",
    },
    candles: {
      symbol_not_found: "Brak świec dla {{symbol}} na OKX/Bybit",
      invalid_interval: "Nieobsługiwany interwał: {{interval}}",
      interval_not_found: "Nie ma takiego interwału na liście: {{interval}}",
      unavailable: "Nie udało się pobrać świec z giełdy",
    },
    prices: {
      refresh_too_soon: "Odczekaj {{retry_after}} s przed kolejnym odświeżeniem",
    },
  },

  validation: {
    default: "Nieprawidłowe dane",
    fee_not_below_quantity: "Opłata musi być mniejsza niż kupiona ilość",
    invalid_symbol: "Symbol coina: same litery i cyfry, np. BTC",
    duplicate_position: "Każda pozycja może wystąpić w sprzedaży tylko raz",
    invalid_tag: "Tagi mogą zawierać tylko litery, cyfry, „_” i „-”",
    too_many_tags: "Za dużo tagów (maks. 20)",
    greater_than: "Wartość musi być większa od zera",
    greater_than_equal: "Wartość nie może być ujemna",
    string_too_short: "Pole jest za krótkie",
    string_too_long: "Pole jest za długie",
    missing: "Brakuje wymaganego pola",
    value_error: "Nieprawidłowa wartość",
  },
};
