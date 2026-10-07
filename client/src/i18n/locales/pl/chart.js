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
  },
  intervals: {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
  },
};
