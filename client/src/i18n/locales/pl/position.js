// Formularz zakupu (dodawanie i edycja pozycji).
export default {
  newTitle: "Nowy zakup",
  editTitle: "Edycja zakupu {{symbol}}",
  coin: "Coin",
  symbolLocked: "Pozycja ma sprzedaże, więc coina nie można zmienić.",
  buyPrice: "Cena zakupu ({{currency}})",
  useCurrent: "Użyj aktualnej: {{price}}",
  quantity: "Ilość (kupiona)",
  fee: "Opłata (w {{symbol}})",
  feeCoinFallback: "coinie",
  feeHint: "Jak na giełdzie: opłata pobrana z kupionej ilości.",
  date: "Data zakupu",
  preview: {
    cost: "Koszt",
    held: "Na koncie",
    resultNow: "Wynik teraz",
  },
  submitNew: "Dodaj zakup",
  // Dziennik transakcji (wszystko opcjonalne).
  journal: {
    entryReason: "Powód wejścia",
    entryReasonPlaceholder: "Np. spadek do wsparcia, RSI 30m < 30, cena pod dolną Bollinger Band",
    tags: "Tagi (opcjonalnie)",
    tagsHint: "Oddziel przecinkami, np. RSI, SUPPORT, BB.",
    targetPrice: "Target / TP ({{currency}})",
    stopLoss: "Stop loss / SL ({{currency}})",
    plan: "Plan",
  },
  errors: {
    chooseCoin: "Wybierz coina",
    invalidPrice: "Podaj poprawną cenę zakupu",
    invalidQuantity: "Podaj poprawną ilość",
    invalidFee: "Podaj poprawną opłatę (lub zostaw puste)",
    feeTooHigh: "Opłata musi być mniejsza niż ilość",
    invalidTargets: "Podaj poprawny TP / SL (lub zostaw puste)",
  },
};
