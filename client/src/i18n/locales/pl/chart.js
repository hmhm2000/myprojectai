// Wykres świecowy.
export default {
  source: "Świece: {{source}}",
  // Transakcje (z dziennika) na wykresie.
  trades: {
    title: "Twoje transakcje {{symbol}}",
    none: "Brak transakcji na tym coinie.",
    hint: "Kliknij strzałkę BUY/SELL na wykresie albo wiersz na liście, aby zobaczyć wpis z dziennika.",
    entryReason: "Powód",
    exitReason: "Powód wyjścia",
    plan: "Plan",
    fromPosition: "{{quantity}} z zakupu {{date}} po {{price}}",
    showAll: "Pokaż transakcje na wykresie",
    showOnChart: "Pokaż na wykresie",
    hideOnChart: "Ukryj na wykresie",
  },
  // Wskaźniki na wykresie (liczone na serwerze).
  indicators: {
    title: "Wskaźniki",
    add: "Dodaj",
    addTitle: "Nowy wskaźnik",
    editTitle: "Ustawienia: {{name}}",
    empty: "Brak wskaźników. Dodaj np. SMA, RSI albo Bollinger Bands.",
    indicator: "Wskaźnik",
    interval: "Interwał wskaźnika",
    intervalHint: "Np. SMA 100 z 1D na wykresie 1H. Historia pokazuje tylko zamknięte świece tego interwału.",
    followChart: "Jak wykres",
    ownInterval: "liczony z {{interval}}",
    chartInterval: "jak wykres ({{interval}})",
    edit: "Edytuj",
    hide: "Ukryj",
    show: "Pokaż",
    remove: "Usuń",
    reset: "Przywróć domyślne",
  },
  // Nazwy parametrów wskaźników (klucze z backendu).
  params: {
    length: "okres",
    source: "źródło",
    mult: "mnożnik",
    fast: "szybka",
    slow: "wolna",
    signal: "sygnał",
    k_length: "%K okres",
    k_smoothing: "%K wygł.",
    d_smoothing: "%D wygł.",
  },
  // Jednostki interwałów w etykietach ("4h", "3D", "2W", "1M"); m = minuty, M = miesiące.
  units: { m: "m", h: "h", d: "D", w: "W", M: "M" },
  // Własny interwał wpisywany obok przycisków.
  customInterval: {
    placeholder: "np. 3D",
    hint: "Własny interwał: liczba + jednostka (m, h, D, W, M), np. 3D, 2W, 2h, 3M. M = miesiąc, m = minuta.",
    add: "Dodaj",
    invalid: "Nieprawidłowy interwał (np. 3D, 2W, 45m; maks. 1 rok).",
    remove: "Usuń z listy",
  },
};
