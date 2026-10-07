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
  errors: {
    chooseCoin: "Wybierz coina",
    invalidPrice: "Podaj poprawną cenę zakupu",
    invalidQuantity: "Podaj poprawną ilość",
    invalidFee: "Podaj poprawną opłatę (lub zostaw puste)",
    feeTooHigh: "Opłata musi być mniejsza niż ilość",
  },
};
