# Crypto Tracker: przebudowa, notatki z etapów

Ten plik zbiera podsumowania kolejnych etapów: co się zmieniło, jak to uruchomić i jak przetestować.

## Szybki start

```powershell
# Terminal 1: backend
cd C:\Users\micha\wallet_project\server
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 5000

# Terminal 2: frontend
cd C:\Users\micha\wallet_project\client
npm run dev
```
Otwórz http://localhost:3000 i zaloguj się jako `admin`. Hasło jest w `server/.env` (`ADMIN_PASSWORD`).

Twoja baza jest już zmigrowana do nowego formatu (konta `dar` i `jan` zostały). Kopia sprzed migracji leży w `server/db/database.pre-v2.bak`.

---

## Założenia (ustalone przed startem)

| Temat | Decyzja |
|---|---|
| Konta | Kod rejestracji zostaje, ale domyślnie jest wyłączony (`ALLOW_REGISTRATION=false` w `server/.env`). Przy wyłączonej rejestracji działa jedno konto główne (admin) z `.env`. |
| Waluta | USDT (`QUOTE_CURRENCY`). |
| Ceny | OKX jako źródło główne, Bybit uzupełnia coiny, których nie ma na OKX (np. SPX). |
| Opłata zakupu | W coinie, jak na giełdzie: kupujesz 1 BTC, opłata 0,001 BTC, na koncie zostaje 0,999 BTC. |
| Opłata sprzedaży | W USDT. |
| Sprzedaż | Przypisana do konkretnej pozycji (zakupu). Formularz podpowiada najstarszą otwartą pozycję (FIFO). |
| Stare dane | Pozycje i ulubione były testowe, więc są usuwane. Konta użytkowników zostają. |

### Wzory (dla jednej pozycji, wszystko w Decimal)

```
koszt           = cena_zakupu × ilość                 (ile USDT wydałeś)
posiadane       = ilość − opłata_w_coinie
otwarte         = posiadane − suma sprzedanych
zrealizowany    = Σ(ilość_sprz × cena_sprz − opłata_USDT) − koszt × (sprzedane / posiadane)
niezrealizowany = otwarte × cena_bieżąca − koszt × (otwarte / posiadane)
zysk całkowity  = zrealizowany + niezrealizowany,   % = zysk / koszt
```

---

## Etap 1: fundament backendu

**Co się zmieniło**
- **Konfiguracja:** `server/config.py` czyta wszystko z `server/.env`. Wzór z opisami jest w `server/.env.example`. Do `.env` dopisane są nowe klucze, a `SECRET_KEY` został bez zmian.
- **Rejestracja:** przełącza ją `ALLOW_REGISTRATION=false/true`. Gdy jest wyłączona, `/api/auth/register` zwraca 403. `GET /api/auth/config` mówi frontendowi, czy pokazać formularz rejestracji.
- **Konto główne:** przy starcie serwer tworzy konto z `ADMIN_USERNAME` (domyślnie `admin`) i `ADMIN_PASSWORD`. Hasło zostało wylosowane i zapisane w `server/.env`, więc można je zmienić przed pierwszym startem. Jeśli w `ADMIN_USERNAME` wpiszesz nazwę istniejącego konta (`dar` albo `jan`), to konto dostanie uprawnienia admina z dotychczasowym hasłem.
- **Model danych:**
  - `models/portfolio.py`: `Portfolio`, `Position`, `Sale`;
  - `models/favorites.py`: `FavoriteList`, `FavoriteCoin`.

  Kwoty są zapisywane jako dokładny tekst (`database/types.py`), a w Pythonie są zawsze `Decimal`. Kaskadowe usuwanie działa też w samym SQLite.
- **Migracja** `b7e3c9a1d2f4`: usuwa stare testowe tabele portfeli i ulubionych i tworzy nowe. Tabela `users` zostaje. Działa też cofanie (`alembic downgrade -1`).
- **`requirements.txt`:** uzupełniony i zainstalowany do `server/venv`. `bcrypt` jest przypięty do wersji 4.0.1, bo nowsze wersje źle współpracują z `passlib`.
- **Testy:** `server/tests/` (pytest), każdy test na osobnej, tymczasowej bazie.

**Jak uruchomić (PowerShell)**
```powershell
cd C:\Users\micha\wallet_project\server
.\venv\Scripts\Activate.ps1
python -m pytest -q                                   # testy
Copy-Item db\database.db db\database.pre-v2.bak       # (opcjonalnie) kopia bazy
alembic upgrade head                                  # migracja prawdziwej bazy
uvicorn main:app --reload --port 5000
```
Na http://localhost:5000/docs:
1. Kliknij **Authorize** i zaloguj się jako `admin` z hasłem z `.env`.
2. `GET /api/auth/me` powinno zwrócić `is_admin: true`.
3. `POST /api/auth/register` powinno zwrócić 403.

**Do zrobienia ręcznie (repo)**
- `server/.env` jest śledzony przez gita i zawiera teraz hasło admina, więc nie commituj go. Śledzone są też plik bazy, `__pycache__` i `wallet_project.zip`. Proponowane polecenia (pliki na dysku zostają):
  ```powershell
  git rm --cached server/.env server/db/database.db server/db/database.db.bak wallet_project.zip
  git rm -r --cached server/**/__pycache__
  ```
  W `.gitignore` trzeba też poprawić wzór `db/database.db` na `**/db/*.db`.

---

## Etap 2: ceny (OKX + Bybit, cache)

**Wybór giełdy:** obie mają równie prosty publiczny endpoint bez klucza, który jednym zapytaniem zwraca wszystkie pary spot:
- OKX: `GET https://www.okx.com/api/v5/market/tickers?instType=SPOT`
- Bybit: `GET https://api.bybit.com/v5/market/tickers?category=spot`

OKX jest źródłem głównym (403 pary USDT, mapowanie było już w projekcie). Bybit uzupełnia coiny, których nie ma na OKX (392 pary USDT, w tym SPX). Łącznie dostępnych jest ok. 590 coinów. Jeśli coin jest na obu giełdach, cena pochodzi z OKX, a pole `source` mówi, skąd jest cena.

**Jak działa cache** (`server/services/price_service.py`)
- **Start serwera:** pierwsze pobranie w tle, bez blokowania startu.
- **`GET /api/prices`:** zwraca dane z pamięci. Giełdy są odpytywane tylko wtedy, gdy dane są starsze niż `PRICE_TTL_SECONDS` (domyślnie 180 s). Gdy nikt nie używa aplikacji, nic nie jest pobierane. Każda giełda to jedno zapytanie zbiorcze, oba idą równolegle, a jednocześnie trwa najwyżej jedno pobieranie.
- **`POST /api/prices/refresh`:** wymusza pobranie nie częściej niż co `PRICE_FORCE_MIN_INTERVAL_SECONDS` (10 s). Częstsze próby dostają HTTP 429 z `retry_after`.
- **Błąd lub limit giełdy** (timeout, HTTP 429, błąd API):
  - zostają ostatnie znane ceny z `stale: true`;
  - pole `fetched_at` mówi, od kiedy ceny są nieaktualne, a `sources[].error` zawiera opis błędu;
  - kolejna próba następuje dopiero po `PRICE_ERROR_BACKOFF_SECONDS` (30 s) albo po czasie z nagłówka `Retry-After`, jeśli giełda poda dłuższy;
  - gdy padnie tylko jedna giełda, ceny z drugiej dalej się aktualizują.
- **Filtrowanie:** `GET /api/prices?symbols=BTC,SPX` zwraca tylko wybrane coiny. Bez parametru zwraca wszystkie i z tego korzysta wyszukiwarka coinów.
- **Precyzja:** kwoty są zwracane jako stringi (Decimal), np. `"0.4187"`.

**Jak przetestować**
```powershell
cd C:\Users\micha\wallet_project\server
.\venv\Scripts\Activate.ps1
python -m pytest -q        # m.in. TTL, backoff, 429, wymuszenie, parsery (bez sieci)
uvicorn main:app --reload --port 5000
```
W `/docs`, po zalogowaniu:
1. `GET /api/prices?symbols=BTC,SPX` zwraca BTC z `okx` i SPX z `bybit`.
2. Kilka kolejnych wywołań w ciągu 3 minut nie daje w logu serwera nowych linii „Pobrano … cen”.
3. `POST /api/prices/refresh` wywołane dwa razy szybko: najpierw 200, potem 429.
4. Symulacja awarii: odłącz internet i wymuś odświeżenie. Odpowiedź ma `stale: true` i błąd w `sources`, a ceny zostają.

---

## Etap 3: API portfeli, pozycji, sprzedaży i ulubionych

**Obliczenia** (`server/services/pnl.py`): czyste funkcje w Decimal, wzory jak na górze pliku.
- Każda pozycja ma własny zysk: zrealizowany ze sprzedaży, niezrealizowany z części otwartej, łączny i w %.
- **Coin** (suma jego pozycji):
  - otwarta ilość;
  - zainwestowane, czyli koszt części otwartej;
  - wartość;
  - zysk niezrealizowany w USDT i w %;
  - zysk zrealizowany;
  - liczba otwartych i zamkniętych pozycji.
- **Portfel:** te same sumy plus lista coinów, dla których nie ma ceny (`missing_prices`). Takie coiny nie wchodzą do wartości, żeby nie fałszować wyniku.
- **Pozycja zamknięta** (cała sprzedana) ma tylko zysk zrealizowany i nie potrzebuje ceny. Nowy zakup to zawsze nowa pozycja.
- **Zaokrąglenia:** kwoty do 8 miejsc po przecinku, procenty do 2. API zwraca je jako stringi.

**Endpointy.** Każda zmiana zwraca od razu przeliczony widok całego portfela.

| Metoda | Ścieżka | Co robi |
|---|---|---|
| GET | `/api/portfolios` | lista portfeli z podsumowaniem |
| POST | `/api/portfolios` | nowy portfel `{name}` |
| GET | `/api/portfolios/{id}` | widok: `summary`, `coins[]` (każdy z `positions[]` i `sales[]`), `prices` (stale/fetched_at) |
| PATCH | `/api/portfolios/{id}` | zmiana nazwy |
| DELETE | `/api/portfolios/{id}` | usunięcie razem z pozycjami (potwierdzenie robi UI) |
| POST | `/api/portfolios/{id}/positions` | zakup `{symbol, buy_price, quantity, fee_coin, bought_at, note}` |
| PUT | `/api/positions/{id}` | edycja zakupu |
| DELETE | `/api/positions/{id}` | usunięcie zakupu (z jego sprzedażami) |
| POST | `/api/positions/{id}/sales` | sprzedaż `{price, quantity, fee_quote, sold_at, note}` |
| PUT | `/api/sales/{id}` | edycja sprzedaży |
| DELETE | `/api/sales/{id}` | usunięcie sprzedaży |
| GET/POST | `/api/favorite-lists` | listy ulubionych |
| PATCH/DELETE | `/api/favorite-lists/{id}` | zmiana nazwy, usunięcie |
| POST | `/api/favorite-lists/{id}/coins` | dodanie coina `{symbol}` (duplikat daje 409) |
| DELETE | `/api/favorite-lists/{id}/coins/{symbol}` | usunięcie coina z listy |

**Walidacja**
- Ceny i ilości muszą być > 0, a opłata ≥ 0.
- Opłata w coinie musi być mniejsza niż kupiona ilość.
- Symbol składa się tylko z liter i cyfr i jest automatycznie zamieniany na wielkie litery.
- Sprzedaż nie może przekroczyć otwartej ilości pozycji.
- Edycja zakupu nie może zejść poniżej ilości już sprzedanej.
- Nie można zmienić coina pozycji, która ma sprzedaże.
- Dane innego użytkownika zwracają 404.

**Jak przetestować**
```powershell
cd C:\Users\micha\wallet_project\server
.\venv\Scripts\Activate.ps1
python -m pytest -q          # 31 testów: wzory, sprzedaże, FIFO, walidacja, izolacja użytkowników
uvicorn main:app --reload --port 5000
```
W `/docs`:
1. Utwórz portfel.
2. Dodaj dwa zakupy tego samego coina po różnych cenach.
3. W `GET /api/portfolios/{id}` każdy zakup ma swój `total_pnl`, a coin ma sumę.

---

## Etapy 4–6: frontend (dark UI, portfele, ulubione, ustawienia)

**Struktura `client/src`**
```
api/client.js         axios z adresem z VITE_API_URL (domyślnie http://localhost:5000) + token; 401 = wylogowanie
api/endpoints.js      wszystkie wywołania API w jednym miejscu
context/              AuthProvider (logowanie), PriceProvider (wspólny cache cen), contexts.js (hooki)
lib/format.js         formatowanie kwot i dat (pl-PL), parsowanie "0,5" -> "0.5", dokładne dodawanie stringów
components/           Layout (menu), Modal, ConfirmDialog, PriceStatusBar, CoinPicker, PositionForm, SaleForm,
                      NameDialog, ui.jsx (Pnl, CoinBadge...), portfolio/ (SummaryCards, CoinRow, PositionRow)
pages/                LoginPage, RegisterPage, PortfoliosPage, FavoritesPage, SettingsPage
```
Usunięte: stare komponenty (`FavoriteList`, `PortfolioSummary`, `CoinSelectionWindow`, `AdminPanel`, `Navbar`, `Login`, `Register`), `data/coins.js`, `App.css`, `api/priceService.js`.

**Widoki**
- **Menu:** Portfele / Ulubione / Ustawienia. Na komputerze jest na górze, na telefonie jako dolny pasek.
- **Portfele:**
  - zakładki portfeli z wartością, przycisk „+ Portfel”, zmiana nazwy i usunięcie (usunięcie wymaga potwierdzenia, okno pokazuje liczbę pozycji);
  - na górze 4 kafelki: Wartość, Zainwestowane, Zysk/strata (USDT i %) oraz Zrealizowany (z wynikiem łącznym);
  - pod nimi pasek cen: godzina pobrania, źródła i przycisk „Odśwież ceny” z licznikiem limitu. Przy awarii giełdy pojawia się żółte ostrzeżenie, od kiedy ceny są nieaktualne;
  - lista coinów: cena z wynikiem 24h i źródłem, ilość, wartość, zainwestowane, zysk/strata w USDT i %;
  - kliknięcie coina płynnie rozwija listę zakupów. Każdy zakup ma własny koszt, wartość i zysk w USDT i %, znacznik „zamknięta” lub „częściowo sprzedana”, opłatę i notatkę oraz pod spodem swoje sprzedaże (z edycją i usuwaniem);
  - akcje: „Kup X”, „Sprzedaj X” (formularz podpowiada najstarszą otwartą pozycję, czyli FIFO), a przy każdym zakupie: sprzedaj, edytuj, usuń.
- **Formularze:**
  - wyszukiwarka coinów z ceną i źródłem (OKX/Bybit) i obsługą klawiatury;
  - przycisk „Użyj aktualnej ceny”, przy sprzedaży także „Maks.”;
  - podgląd kosztu i wyniku przed zapisem;
  - akceptują przecinek jako separator dziesiętny;
  - błędy z backendu (np. zbyt duża sprzedaż) pokazują się w formularzu.
- **Ulubione:**
  - wiele list w zakładkach (dodawanie, zmiana nazwy, usuwanie z potwierdzeniem);
  - coin dodajesz z wyszukiwarki;
  - kafelki pokazują cenę, wynik 24h i źródło;
  - ceny pochodzą z tego samego cache, bez dodatkowych zapytań.
- **Ustawienia:**
  - stan cen (TTL, liczba coinów, stan OKX i Bybit);
  - dane konta i status rejestracji;
  - dla admina lista użytkowników z nadawaniem i odbieraniem roli admina.

**Wygląd**
- Czarne tło z delikatną fioletowo-zieloną poświatą.
- Ciemne kafelki z rozmytym „LED-em” za krawędzią. Kafelek zysku świeci na zielono, straty na czerwono.
- Zysk jest zielony, strata czerwona. Liczby są w czcionce o stałej szerokości cyfr (JetBrains Mono), więc kolumny się nie rozjeżdżają.
- Układ jest responsywny: na telefonie kolumny zamieniają się w opisane pola, okna wysuwają się od dołu, a przewijanie zakładek jest poziome.

**Ceny we frontendzie**
- Po zalogowaniu pobierane są raz z backendu.
- Przełączanie widoków nie wysyła żadnego zapytania o ceny.
- Co 15 s aplikacja sprawdza, czy dane są starsze niż TTL (3 min) i czy karta jest widoczna. Dopiero wtedy pyta backend, a backend sam decyduje, czy odpytać giełdę.
- Widok portfela przelicza się, gdy backend ma nowe ceny.

**Jak przetestować**
```powershell
cd C:\Users\micha\wallet_project\client
npm run lint
npm run build
npm run dev          # http://localhost:3000 (backend musi działać na :5000)
```
Scenariusz ręczny:
1. Utwórz portfel.
2. Dodaj dwa zakupy SPX po różnych cenach i rozwiń SPX. Każdy zakup ma swój zysk.
3. Kliknij „Sprzedaj SPX”: domyślnie wybrana jest najstarsza pozycja (FIFO). Sprzedaj część i sprawdź znacznik „częściowo sprzedana” oraz zysk zrealizowany.
4. Spróbuj sprzedać więcej, niż masz: pojawi się komunikat błędu.
5. Kliknij „Odśwież ceny” dwa razy: drugi raz przycisk pokazuje licznik sekund.
6. Ulubione: utwórz listę „Memecoiny” i dodaj SPX, PEPE, DOGE.
7. Zmniejsz okno do szerokości telefonu: pojawi się dolne menu, a wiersze się przełożą.

Co zostało sprawdzone:
- lint i build czyste;
- 31 testów backendu przechodzi;
- przeglądarka (Edge headless, na kopii bazy): logowanie, dodanie zakupu przez formularz (opłata w coinie), sprzedaż z podpowiedzią FIFO, walidacja zbyt dużej sprzedaży, usunięcie z potwierdzeniem, limit odświeżania, widoki na komputerze i telefonie. Konsola bez błędów (poza celowym 400 z testu walidacji).

**Konfiguracja frontendu:** adres API można zmienić w `client/.env` (wzór `client/.env.example`): `VITE_API_URL=http://localhost:5000`.

---

## Co zostało do ręcznej decyzji

1. **Git:** nic nie zostało zacommitowane. Przed commitem wyjmij z repo `server/.env` (zawiera `SECRET_KEY` i hasło admina) oraz pliki bazy, `__pycache__` i `wallet_project.zip`. Polecenia są w sekcji „Etap 1”. `.gitignore` jest już poprawiony (`**/db/*.db`, `.pytest_cache/`, `!requirements.txt`).
2. **Stare konta `dar` i `jan`:** zostały w bazie. Możesz je zostawić albo usunąć. Przy wyłączonej rejestracji nikt nowy się nie zarejestruje, ale te konta nadal mogą się logować.
3. **Hasło admina:** wylosowane, jest w `server/.env`. Zmiana działa tylko przed pierwszym startem: później konto już istnieje i hasło z `.env` nie jest ponownie wczytywane.

---

## Etap 7: sprzedaż z kilku pozycji, sortowanie, przeciąganie, ukrywanie zamkniętych

**Sprzedaż z jednej lub kilku pozycji**
- Formularz „Sprzedaj X” pokazuje listę otwartych pozycji z polami wyboru. Nic nie jest zaznaczone automatycznie, więc najstarsza pozycja nie jest ruszana bez Twojej decyzji. Przycisk sprzedaży przy konkretnej pozycji zaznacza od razu tę pozycję.
- Wpisujesz **łączną ilość** i zaznaczasz pozycje. Ilość wypełnia je **w kolejności zaznaczania**, a każda zaznaczona pozycja dostaje numer 1, 2, 3… Przykład: wpisujesz 1,5 BTC, zaznaczasz B, potem C. B dostaje całe 1 BTC, a C 0,5 BTC. Pozycja A zostaje nietknięta.
- Ilość przy każdej pozycji możesz poprawić ręcznie, a suma przelicza się sama. Bez wpisanej ilości zaznaczenie pozycji oznacza sprzedaż całej pozycji. Jest też przycisk „Całe zaznaczone”.
- Opłatę (USDT) podajesz łącznie za całą sprzedaż. Backend rozdziela ją proporcjonalnie do ilości i suma części zawsze zgadza się co do grosza.
- Formularz pokazuje przy każdej pozycji, ile da się z niej sprzedać, jej obecny wynik i podgląd zysku z tej części.
- Przy pozycji sprzedaż wyświetla się z dopiskiem „część sprzedaży 1,5 BTC z 2 pozycji”. Edycja i usunięcie działają na całej sprzedaży naraz.

**Jak to jest zapisane:** jedna sprzedaż to grupa wierszy `sales` ze wspólnym `group_id`, po jednym wierszu na pozycję. Każda pozycja dalej ma więc własny, dokładny zysk.

API:
- `POST /api/portfolios/{id}/sales` z polami `{price, fee_quote, sold_at, note, allocations: [{position_id, quantity}]}`;
- `PUT /api/sale-groups/{group_id}` i `DELETE /api/sale-groups/{group_id}`;
- stare `/api/positions/{id}/sales` i `/api/sales/{id}` zostały usunięte.

Walidacja:
- wszystkie pozycje w jednej sprzedaży muszą być tego samego coina;
- z żadnej pozycji nie można sprzedać więcej, niż jest dostępne (przy edycji liczy się bez starej wersji tej sprzedaży);
- każda pozycja może wystąpić w sprzedaży tylko raz.

**Sortowanie i własna kolejność**
- W rozwiniętym coinie jest pole „Sortuj”: własna kolejność, data (najnowsze/najstarsze), cena zakupu (rosnąco/malejąco), zysk % (najwyższy/najniższy), ilość. Wybór zapamiętuje się osobno dla każdego coina, w przeglądarce.
- Kolejność zmieniasz, przeciągając za uchwyt ⠿ po lewej stronie pozycji. Działa myszą i palcem. Po upuszczeniu kolejność zapisuje się na serwerze (`positions.sort_order`), a sortowanie przełącza się na „Własna kolejność”. Gdy wybierzesz inne sortowanie, układ się zmieni, a własna kolejność czeka zapisana.
- API: `PUT /api/portfolios/{id}/positions/order` z polem `{position_ids: [...]}`.

**Zamknięte pozycje i zysk**
- Zamknięte pozycje (całe sprzedane) są **domyślnie ukryte**. Coin, który ma tylko zamknięte pozycje, też znika z listy. Przycisk „Pokaż zamknięte (N)” pokazuje historię, a „Ukryj zamknięte” znowu ją chowa. Wybór jest zapamiętany.
- Kafelki na górze:
  - **Zysk otwartych pozycji:** tylko to, co teraz trzymasz (kwota i %);
  - **Zysk ogólny:** zrealizowany (także z zamkniętych, ukrytych pozycji) plus otwarte; procent liczony od kosztu wszystkich zakupów. Pod spodem jest „w tym zrealizowany”.
- Wiersz coina pokazuje zysk otwartych pozycji, a pod nim „ogólny”, jeśli coś już sprzedałeś.

**Migracja** `c4d8e2f6a913` (Twoja baza jest już zaktualizowana):
- dodaje `positions.sort_order`: istniejące pozycje dostały kolejność według daty zakupu;
- dodaje `sales.group_id`: każda istniejąca sprzedaż dostała własną grupę;
- działa też cofanie (`alembic downgrade -1`).

**Jak przetestować**
```powershell
cd C:\Users\micha\wallet_project\server
.\venv\Scripts\Activate.ps1
python -m pytest -q          # 37 testów, w tym sprzedaż z kilku pozycji, podział opłaty, edycja/usuwanie grupy, kolejność
```
Scenariusz ręczny:
1. Dodaj 3 zakupy BTC (np. 1 BTC każdy).
2. „Sprzedaj BTC”: wpisz 1,5 i zaznacz najpierw trzecią, potem drugą pozycję. Trzecia dostaje 1, druga 0,5, a pierwsza zostaje nietknięta.
3. Zapisz. Trzecia pozycja znika, bo jest zamknięta. „Pokaż zamknięte” ją pokazuje, a przy obu pozycjach widać „część sprzedaży 1,5 BTC z 2 pozycji”.
4. Edytuj tę sprzedaż i zmień ręcznie ilość przy jednej pozycji. Suma się przeliczy.
5. Zmień sortowanie (np. „Cena zakupu: najwyższa”). Potem przeciągnij pozycję za ⠿ i odśwież stronę: kolejność zostaje.

Co zostało sprawdzone w przeglądarce (Edge headless, kopia bazy):
- ukrywanie i pokazywanie zamkniętych;
- kafelki zysku otwartych i ogólnego;
- brak automatycznego zaznaczania;
- rozdział ilości w kolejności zaznaczania;
- zapis sprzedaży z 2 pozycji;
- edycja z ręczną zmianą podziału;
- sortowanie po cenie w obie strony;
- przeciąganie z zapisem po odświeżeniu;
- usunięcie całej sprzedaży;
- formularz na telefonie.

Wszystkie 16 sprawdzeń przeszło, a w konsoli nie było błędów.

**Uwaga o gicie:** na początku przebudowy usuwałem stare pliki poleceniem `git rm`, więc te usunięcia są już „zastage’owane” w indeksie (nic nie zostało zacommitowane). Zobaczysz je w `git status` jako `D`. Commit robisz sam.

---

## Etap 8: średnia cena zakupu otwartych pozycji

- W wierszu każdego coina jest nowa kolumna **„Śr. cena zakupu”**. To cena zakupu otwartych pozycji, ważona ilością, która na każdej pozycji **jeszcze została**:
  - po sprzedaży części pozycji jej waga maleje;
  - po zamknięciu pozycji przestaje się liczyć;
  - średnia przelicza się sama przy każdej zmianie.

  Przykład: 1 BTC po 40 000 i 1 BTC po 60 000 daje średnią 50 000. Po sprzedaży 0,5 z tańszej pozycji średnia wynosi (40 000×0,5 + 60 000×1) / 1,5 = 53 333,33.
- Pod średnią widać **„z opłatą”**, czyli próg rentowności: koszt otwartej części podzielony przez otwartą ilość. Uwzględnia opłatę pobraną w coinie (kupujesz 1 BTC po 50 000, opłata 0,001 BTC, więc próg wynosi 50 050,05). Pokazuje się tylko wtedy, gdy różni się od średniej.
- API: każdy coin w `GET /api/portfolios/{id}` ma pola `avg_buy_price` i `break_even_price`. Gdy coin nie ma otwartych pozycji, oba mają wartość `null`.
- Testy: `server/tests/test_average_price.py` (średnia ważona, aktualizacja po sprzedaży częściowej i całkowitej, próg z opłatą, test przez API). Razem przechodzi 42 testy.

**Repozytorium:** od tej zmiany pracuję na gałęziach w `hmhm2000/myprojectai`. Każda zmiana idzie na osobnej gałęzi `feature/...` z opisanymi commitami i trafia do `master` przez Pull Request. Przy okazji zdjąłem ze śledzenia `.continue/` (lokalna konfiguracja edytora, plik na dysku został) i dodałem go do `.gitignore`.

---

## Etap 9: teksty w osobnych plikach (i18n), kod po angielsku

**Gdzie są teksty:** wszystkie teksty interfejsu leżą w `client/src/i18n/locales/pl/`, podzielone na pliki według obszaru:

| Plik | Co zawiera |
|---|---|
| `common.js` | **nazwa aplikacji i logo**, wspólne przyciski (Anuluj, Zapisz…), „Ładowanie…” |
| `nav.js` | menu: Portfele, Ulubione, Ustawienia, Wyloguj |
| `auth.js` | logowanie i rejestracja |
| `prices.js` | pasek cen, przycisk „Odśwież ceny”, nazwy giełd, błędy giełd |
| `coins.js` | wyszukiwarka coinów |
| `portfolio.js` | strona portfela: kafelki, kolumny, wiersz coina, pozycje, sortowanie, okna potwierdzeń |
| `position.js` | formularz zakupu |
| `sale.js` | formularz sprzedaży |
| `favorites.js` | ulubione |
| `settings.js` | ustawienia |
| `errors.js` | komunikaty błędów, także tych z backendu |

W `locales/pl/index.js` są też format liczb i dat (`pl-PL`) oraz symbol waluty (`$`).

**Jak zmienić tekst:** znajdź go w odpowiednim pliku i podmień wartość w cudzysłowie.
- `{{nazwa}}` to miejsce na wartość wstawianą przez kod, np. `"Sprzedaj {{symbol}}"`. Nawiasy z nazwą zostaw, przenosić je w zdaniu możesz.
- Obiekty `{ one, few, many, other }` to formy liczby mnogiej (1 pozycja / 2 pozycje / 5 pozycji).

**Zmiana nazwy strony:** w `common.js` zmień `app.name` (tytuł karty) oraz `app.logoMain` i `app.logoAccent` (logo).

**Nowy język** (np. angielski):
1. Skopiuj folder `locales/pl` jako `locales/en` i przetłumacz wartości.
2. W `client/src/i18n/index.js` dopisz `import en from "./locales/en";` i dodaj `en` do `LOCALES`.
3. W `client/.env` ustaw `VITE_LANGUAGE=en` i zrestartuj `npm run dev`.

**Pilnowanie porządku:** `npm run check:i18n` (w `client/`) sprawdza, czy każdy klucz użyty w kodzie istnieje w plikach językowych i czy poza nimi nie ma polskich znaków, czyli tekstu wpisanego na sztywno.

**Backend po angielsku:**
- Logi, komentarze, docstringi i `.env.example` są po angielsku.
- Błędy API mają format `{"detail": "...po angielsku...", "code": "sale.exceeds_available", "params": {...}}`. Frontend tłumaczy `code` przez `errors.api.<code>` w `errors.js`, a parametry wstawia sformatowane po polsku, np. datę i ilość. Nowy błąd w backendzie wymaga więc tylko dopisania jednej linijki w `errors.js`.
- Błędy walidacji (422) mają własne typy (`fee_not_below_quantity`, `invalid_symbol`, `duplicate_position`), tłumaczone przez `errors.validation.<typ>`.
- Błędy giełd mają kod w `sources[].error_code` (`connection_error`, `rate_limited`, …), tłumaczony w `prices.js`.

**Testy:**
- backend: 45 testów, w tym nowy `test_error_codes.py`, który pilnuje formatu błędów;
- frontend: lint, build i `check:i18n` czyste;
- przeglądarka: cały scenariusz z etapu 7 (16 sprawdzeń) na wersji z i18n, do tego polski błąd logowania z kodu, polski błąd z backendu z parametrami („Ilość po opłacie nie może być mniejsza niż już sprzedana (0,04 BTC)”), okna potwierdzeń z pogrubioną nazwą i zero ostrzeżeń o brakujących tłumaczeniach.

**Gałąź:** `feature/i18n` jest założona na `feature/average-buy-price` (te same pliki). Najpierw scal PR z średnią ceną, potem ten. Jeśli otworzysz PR z `feature/i18n` do `master` od razu, będzie zawierał oba zestawy zmian.
