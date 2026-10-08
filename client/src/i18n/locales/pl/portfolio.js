// Portfele: strona portfela, podsumowanie, lista coinów, pozycje (zakupy) w coinie.
export default {
  page: {
    loadingList: "Ładowanie portfeli…",
    loadingOne: "Ładowanie portfela…",
    loadListFailed: "Nie udało się wczytać portfeli",
    loadFailed: "Nie udało się wczytać portfela",
    saveOrderFailed: "Nie udało się zapisać kolejności",
    newPortfolio: "Portfel",
    imported: "Importowane",
    manual: "Ręczne",
    rename: "Zmień nazwę",
    delete: "Usuń portfel",
    coins: "Coiny",
    addPosition: "Dodaj zakup",
    showClosed: "Pokaż zamknięte ({{count}})",
    hideClosed: "Ukryj zamknięte",
    closedHint: "Zamknięte pozycje są zawsze wliczone do zysku ogólnego",
  },

  empty: {
    noPortfolioTitle: "Nie masz jeszcze portfela",
    noPortfolioText: "Portfel grupuje Twoje zakupy. Możesz mieć ich kilka, np. „Długoterminowy” i „Trading”.",
    createPortfolio: "Utwórz portfel",
    allClosedTitle: "Wszystkie pozycje są zamknięte",
    allClosedText: "Kliknij „Pokaż zamknięte”, aby zobaczyć historię. Ich wynik jest wliczony do zysku ogólnego.",
    emptyTitle: "Portfel jest pusty",
    emptyText: "Dodaj pierwszy zakup: coin, cenę, ilość, opłatę i datę. Każdy zakup jest osobną pozycją z własnym wynikiem.",
  },

  dialogs: {
    createTitle: "Nowy portfel",
    renameTitle: "Zmień nazwę portfela",
    deleteTitle: "Usunąć portfel?",
    deleteConfirm: "Usuń portfel",
    deleteMessage: "Portfel {{name}} zostanie usunięty razem ze wszystkimi pozycjami ({{count}}) i sprzedażami.",
    deleteWarning: "Tej operacji nie można cofnąć.",
    deletePositionTitle: "Usunąć zakup?",
    deletePositionMessage: "Zakup {{amount}} po {{price}} z {{date}} zostanie usunięty.",
    deletePositionSales: {
      one: "Usunięta zostanie też jego sprzedaż.",
      few: "Usunięte zostaną też jego sprzedaże ({{count}}).",
      many: "Usunięte zostaną też jego sprzedaże ({{count}}).",
      other: "Usunięte zostaną też jego sprzedaże ({{count}}).",
    },
    deleteSaleTitle: "Usunąć sprzedaż?",
    deleteSaleMessage: "Sprzedaż {{amount}} po {{price}} z {{date}} zostanie usunięta, a ilość wróci do pozycji.",
    deleteSaleShared: {
      one: "Obejmuje 1 pozycję.",
      few: "Obejmuje {{count}} pozycje.",
      many: "Obejmuje {{count}} pozycji.",
      other: "Obejmuje {{count}} pozycji.",
    },
  },

  // Kafelki podsumowania na górze portfela.
  summary: {
    value: "Wartość",
    invested: "Zainwestowane",
    investedHint: "koszt otwartych pozycji",
    openPnl: "Zysk otwartych pozycji",
    totalPnl: "Zysk ogólny",
    includingRealized: "w tym zrealizowany:",
    missingPrices: "Brak aktualnej ceny dla: {{symbols}}. Te coiny nie są wliczone do wartości i zysku.",
  },

  // Nagłówki kolumn listy coinów.
  columns: {
    coin: "Coin",
    quantity: "Ilość",
    avgBuyPrice: "Śr. cena zakupu",
    avgBuyPriceHint: "Ważona ilością, która została na otwartych pozycjach",
    value: "Wartość",
    invested: "Zainwestowane",
    pnl: "Zysk / strata",
  },

  // Wiersz coina i jego rozwinięty panel.
  coin: {
    openCount: "{{count}} otw.",
    closedCount: "{{count}} zamk.",
    closedLabel: "zamknięte",
    overall: "ogólny:",
    withFee: "z opłatą {{price}}",
    withFeeHint: "Koszt otwartej części / ilość - z opłatą pobraną w coinie",
    sortLabel: "Sortuj",
    hiddenClosed: {
      one: "1 zamknięta ukryta",
      few: "{{count}} zamknięte ukryte",
      many: "{{count}} zamkniętych ukrytych",
      other: "{{count}} zamkniętych ukrytych",
    },
    dragHint: "przeciągnij ⠿, aby ustawić własną kolejność",
    allHidden: "Wszystkie pozycje są zamknięte i ukryte.",
    sell: "Sprzedaj {{symbol}}",
    buy: "Kup {{symbol}}",
    chart: "Wykres",
    realizedFooter: "Zrealizowany na {{symbol}} (też z zamkniętych):",
  },

  // Sortowanie pozycji w coinie.
  sort: {
    custom: "Własna kolejność",
    date_desc: "Data zakupu: najnowsze",
    date_asc: "Data zakupu: najstarsze",
    price_asc: "Cena zakupu: najniższa",
    price_desc: "Cena zakupu: najwyższa",
    pnl_desc: "Zysk %: najwyższy",
    pnl_asc: "Zysk %: najniższy",
    qty_desc: "Ilość: największa",
  },

  // Nagłówki kolumn pozycji (zakupów) w rozwiniętym coinie.
  positionColumns: {
    date: "Data zakupu",
    buyPrice: "Cena zakupu",
    quantity: "Ilość otwarta / na koncie",
    cost: "Koszt",
    value: "Wartość",
    pnl: "Zysk / strata",
  },

  // Czas trwania pozycji i czas pod/nad ceną wejścia.
  timing: {
    openFor: "Otwarta od {{duration}}",
    heldFor: "Trwała {{duration}}",
    load: "Czas pod / nad ceną wejścia",
    below: "pod wejściem {{duration}} ({{pct}})",
    above: "nad wejściem {{duration}}",
  },

  // Jedna pozycja (zakup) i jej sprzedaże.
  position: {
    date: "Data",
    buyPrice: "Cena zakupu",
    quantity: "Ilość (otwarta / na koncie)",
    cost: "Koszt",
    value: "Wartość",
    pnl: "Zysk / strata",
    closed: "zamknięta",
    partiallySold: "częściowo sprzedana",
    includingRealized: "w tym zrealizowany:",
    fee: "opłata:",
    drag: "Przeciągnij, aby zmienić kolejność",
    sell: "Sprzedaj z tej pozycji",
    edit: "Edytuj zakup",
    delete: "Usuń zakup",
    saleChip: "sprzedaż",
    saleFee: "opłata {{amount}}",
    sharedSale: "część sprzedaży {{amount}} z {{count}} pozycji",
    sharedSaleHint: "Ta sprzedaż obejmuje kilka pozycji",
    editSale: "Edytuj sprzedaż",
    deleteSale: "Usuń sprzedaż",
  },
};
