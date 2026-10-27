// Strona „Transfery (test)”: wpłaty i wypłaty między giełdami - tylko podgląd, nic nie zmienia w portfelach.
export default {
  title: "Transfery (test)",
  intro: "Podgląd na próbę: wpłaty i wypłaty z plików w folderze importu, połączone między giełdami. Nic tu nie zmienia portfeli, pozycji ani tabel - zapisuje się tylko Twoje oznaczenie adresów.",
  loading: "Liczenie…",
  exchanges: { binance: "Binance", okx: "OKX", bybit: "Bybit.eu", bybit_com: "Bybit.com" },
  files: {
    title: "Pliki wpłat i wypłat ({{count}})",
    summary: "{{deposits}} wpłat i {{withdrawals}} wypłat (tylko ukończone)",
    otherStatus: "{{count}} nieukończonych pominiętych",
  },
  balances: {
    title: "Salda: handel + wpłaty − wypłaty",
    hint: "Handel = zakupy − sprzedaże z importu. Wypłaty z prowizją sieci. Ujemne saldo = brakuje danych (np. zakupy przez Convert / „Kup kryptowaluty” albo wpłaty spoza pliku). Stablecoiny pominięte.",
    noFiles: "brak plików wpłat i wypłat",
    columns: { coin: "Coin", traded: "Handel", deposits: "Wpłaty", withdrawals: "Wypłaty", balance: "Saldo", value: "Wartość" },
  },
  moves: {
    title: "Przeniesienia między Twoimi giełdami ({{count}})",
    hint: "Wypłata z jednej giełdy i wpłata na drugą z tym samym TXID.",
    columns: { date: "Wysłano", coin: "Coin", route: "Skąd → dokąd", amount: "Ilość", minutes: "Czas", txid: "TXID" },
    minutes: "{{n}} min",
  },
  addresses: {
    title: "Adresy, na które wypłacałeś ({{count}})",
    hint: "Oznacz swoje portfele - wtedy liczą się do „Prywatne”. „Obcy” wyklucza adres z dopasowań powrotów.",
    owner: { own: "Mój portfel", foreign: "Obcy", none: "—" },
    labelPlaceholder: "Nazwa (np. Phantom)",
    columns: { address: "Adres", coins: "Wysłano", returned: "Wróciło na giełdę", dates: "Okres", owner: "Czyj", label: "Nazwa" },
    saved: "Zapisano",
  },
  returns: {
    title: "Prawdopodobne powroty z Twoich portfeli ({{count}})",
    hint: "Wpłaty bez pary TXID, pokryte wcześniejszymi wypłatami tego coina (najstarsze najpierw) - to zgadywanie, sprawdź.",
    columns: { date: "Wpłynęło", coin: "Coin", to: "Na", amount: "Ilość", from: "Z wypłat" },
  },
  external: {
    title: "Wpłaty z zewnątrz ({{count}})",
    hint: "Bez pary i bez pasujących wcześniejszych wypłat - cena zakupu nieznana (np. ETH z Zondy).",
    columns: { date: "Data", exchange: "Giełda", coin: "Coin", amount: "Ilość", network: "Sieć" },
  },
  private: {
    title: "Prywatne (Twoje portfele)",
    empty: "Oznacz adresy jako „Mój portfel”, żeby zobaczyć, ile coinów jest poza giełdami.",
    columns: { coin: "Coin", sent: "Wysłano", returned: "Wróciło", balance: "Zostało", value: "Wartość" },
  },
};
