# Audyt DAP i przepływu analizy — 2026-08-29

## Zakres i zasada audytu

Audyt objął cały kod wdrożeniowy, wszystkie trasy HTTP, schemat SQLite,
adaptery źródeł, kalkulację v30 i moment zapisu wyniku. Zmiany rozpoczęto dopiero
po odtworzeniu błędu oraz sprawdzeniu rzeczywistego meczu Liverpool — Nottingham
Forest (Premier League, 2026-08-29, 11:30 UTC).

Kontrakt docelowy jest zgodny z MASTER v11.3 / PR-17.2 i DAP v11: DAP jest
właścicielem danych, zamyka niemutowalny Output Contract i dopiero status
`READY FOR ENGINE 1` ze wszystkimi krytycznymi pozycjami pozwala uruchomić
silnik. `FAIL` oznacza `STOP`.

## Stan przed zmianą — przyczyna źródłowa

W aplikacji nie istniał DAP, automat stanów ani Output Contract. UI i zapis
były połączone bezpośrednio z funkcją `model()`.

Zidentyfikowano trzy niezależne obejścia:

1. `/select/scan` po zakończeniu skanu brał pierwsze cztery rekordy, uruchamiał
   `fetch_stats()`, `model()` i wykonywał `INSERT`, nawet bez decyzji użytkownika.
2. `/select/master` przy braku zaznaczenia automatycznie wybierał kolejkę
   MASTER, uruchamiał model i zapisywał wyniki.
3. `/analyze` wykonywał `model()` i bezpośredni `INSERT` bez weryfikacji
   tożsamości meczu, krytycznych pól i integralności.

Dodatkowo samo renderowanie strony z nazwą zespołu wywoływało `model()`. Pasek
postępu był niezależnym timerem JavaScript, a nie stanem DAP. Wynik mógł więc
pojawić się i zostać zapisany przed zebraniem danych, ponieważ aplikacja nie
posiadała etapu, który dałoby się „zakończyć” lub sprawdzić.

## Audyt źródeł na rzeczywistym meczu

| Źródło | Rzeczywista odpowiedź | Użycie po zmianie |
|---|---|---|
| PremierLeague.com / Pulse | 4 mecze dnia; cel: Liverpool — Nott'm Forest, fixture 128939, 11:30 UTC, Anfield, Gameweek 2, status planowany | Klasa A; para, kickoff, rozgrywki/faza, stadion, neutral venue, status i tabela |
| ESPN `eng.1` | 4 mecze dnia; cel: event 401879314, 11:30 UTC, Anfield, `STATUS_SCHEDULED` | Niezależne potwierdzenie terminarza i tabeli |
| TheSportsDB daily | 3 mecze piłkarskie, bez badanego meczu | Jawne `SUCCESS` dla odpowiedzi dziennej, ale bez fałszywego potwierdzenia celu |
| TheSportsDB search | 1 dopasowany mecz, event 2494012, 11:30 UTC, Anfield, `NS` | Niezależne potwierdzenie konkretnego meczu |
| Football-Data 2026/27 | 10 zakończonych meczów ligi przed cutoff | Bieżący sezon, statystyki historyczne; rekordy po cutoff są odrzucane |
| Football-Data 2025/26 | 380 zakończonych meczów | Uzupełnienie małej próby, jawnie oznaczone jako użycie poprzedniego sezonu |
| Understat 2026/27 | Po 1 meczu obu drużyn przed cutoff; Liverpool xG 3.131 / xGA 1.595, Forest xG 0.657 / xGA 0.466 | Bieżące xG/xGA z ostrzeżeniem o małej próbie |
| API-Football | Brak `API_FOOTBALL_KEY` | `NOT_CONFIGURED`; nie jest liczone jako źródło działające |
| Sportmonks | Brak `SPORTMONKS_TOKEN` | `NOT_CONFIGURED`; nie jest liczone jako źródło działające |

Poprzedni adapter Understat szukał nieaktualnego fragmentu JavaScript i zwracał
brak xG. Nowy adapter używa aktualnego endpointu AJAX. Poprzedni Football-Data
był na stałe przypięty do sezonu 2025/26; nowy wybiera sezon z daty meczu,
pobiera bieżący i poprzedni sezon oraz blokuje dane po cutoff.

## Wynik DAP dla meczu testowego

- DAP: `LIMITED`
- Handover: `READY FOR ENGINE 1`
- DC 81.82, SC 73.79, DF 81.82, DI 80.00, FDC 79.23
- Krytyczne `D01`, `D02`, `D03`, `D04`, `D-STATUS`, `D09`: kompletne
- Brakujące obowiązkowe: `D06`, `D07`, `D12`, `D-TIMING`
- Ostrzeżenia: mała bieżąca próba xG oraz brak części danych obowiązkowych
- Rola prematch: rozwiązana przez algorytm `ROLE-P11.0.2`

Status `LIMITED` jest dopuszczony do silnika tylko dlatego, że wszystkie
pozycje krytyczne są potwierdzone. Gdy dowolna krytyczna pozycja jest brakująca
albo ma nierozwiązany konflikt, kontrakt kończy się `FAIL / STOP`.

## Poprawka globalna

Jedyny dozwolony przepływ to:

`CREATED → DAP_RUNNING → READY_FOR_ENGINE_1 | DAP_BLOCKED → ENGINES_RUNNING → READY_TO_SAVE → COMPLETED`

Zasady wykonawcze:

- `PipelineRunner` jest wspólną ścieżką dla `/analyze` i przekazania z MASTER.
- SELECT tylko skanuje; nie uruchamia DAP, silnika ani zapisu.
- Brak zaznaczenia w MASTER nie powoduje automatycznego wyboru.
- Silnik dostaje wyłącznie zamrożony `immutable_facts_package.engine_input`.
- Hash Output Contract wykrywa modyfikację po zamknięciu DAP.
- Jedyny `INSERT INTO analyses` znajduje się w transakcyjnym
  `finalize_analysis()` i wymaga stanu `READY_TO_SAVE`.
- Uruchomienia i zdarzenia DAP są audytowane oddzielnie od wyników końcowych.
  Zablokowany DAP pozostawia ślad audytowy, ale nie tworzy analizy w historii.
- Zapis jest idempotentny według `run_id`.
- Kursy zastępcze, fikcyjne sygnały rynku, demo-historia i sztuczne wykresy
  zostały usunięte z czynnego przepływu.
- Status każdego adaptera jest jawny: `SUCCESS`, `EMPTY`, `FAILED`,
  `NOT_CONFIGURED` lub `INVALID`.

## Weryfikacja

Automatyczne testy obejmują:

- brak krytycznego DAP → zero wywołań silnika i zero zapisów;
- `LIMITED` z kompletnymi krytycznymi → handover do silnika;
- wykrycie modyfikacji zamrożonego kontraktu;
- awarię silnika bez częściowego zapisu;
- blokadę bezpośredniego zapisu poza `READY_TO_SAVE`;
- idempotentny zapis;
- kolejność DAP → silnik → persistence;
- scalanie aliasów zespołów i pierwszeństwo źródła oficjalnego;
- statyczną kontrolę, że `main.py` nie zawiera bezpośredniego finalnego INSERT,
  a `model()` ma tylko jednego autoryzowanego wywołującego.

Pełny test przez funkcje aplikacji na rzeczywistym meczu zakończył się w 35.91 s:
`COMPLETED`, jeden zapis analizy, 16 kolejnych zdarzeń audytowych; pierwsze
zdarzenie silnika wystąpiło dopiero po zamknięciu kontraktu DAP, a persistence
dopiero po zakończeniu silnika.

## Jawne ograniczenia pozostające poza tą poprawką

Repozytorium zawiera istniejący, uproszczony model v30 (`flow`, `exact`,
`model`), a nie implementację 14 silników opisanych w dokumentacji MASTER.
Poprawka gwarantuje właściwe bramkowanie i zapis dla obecnego modelu, ale nie
udaje, że brakujące silniki zostały zaimplementowane.

API-Football i Sportmonks pozostają nieaktywne bez sekretów środowiskowych.
Ścieżkę bazy można ustawić przez `QE_DB_PATH`; na hostingu należy wskazać trwały
dysk, jeśli historia ma przetrwać odtworzenie instancji.
