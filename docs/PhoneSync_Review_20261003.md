# PhoneSync — ocena projektu i propozycje wymagań

Data: 2026-10-03

## Zakres i charakter oceny

Przeanalizowano SCAN_PHONE.md i scan_phone.py w repozytorium PhoneAccess oraz README.md, docs/, src/, tests/, konfigurację i zależności PhoneSync. Dokument przedstawia stan zastany i propozycje; nie jest opisem wdrożonych zmian. Nie zmieniono kodu projektu.

Sprawdzono składnię pięciu modułów src i wykonano izolowane sprawdzenie detektora ADB na przykładowym wyniku polecenia. Nie uruchamiano pełnej suite testów: testy integracyjne zapisują artefakty w osobistym katalogu, a E2E wykonuje rzeczywiste kopiowanie.

## 1. Ocena ogólna

Projekt ma sensowny cel i użyteczny szkielet, ale obecnie jest prototypem wymagającym napraw przed użyciem do rzeczywistych kopii. Istnieją konfiguracja, podział odpowiedzialności, porównywanie z historią kopii oraz logowanie. Największe braki dotyczą dostępu do telefonu, wiarygodnych metadanych i raportowania błędów.

Nie ma potrzeby przepisywania wszystkiego od początku. Warto zachować działające elementy lokalnego zarządzania plikami i uporządkować przepływ skanowanie → plan przyrostu → kopiowanie.

## 2. Rozumienie dotychczasowych wymagań

- Windows, telefon Android podłączony przez USB/MTP.
- Telefon pozostaje tylko do odczytu.
- YAML określa foldery źródłowe, wykluczenia i katalog docelowy.
- Pusta lista źródeł oznacza cały zakres dostępny przez MTP.
- Skanowanie obejmuje podfoldery.
- Każde uruchomienie kopiowania zapisuje przyrost w osobnym Sync_<timestamp>_<Phone_Name>, zachowując strukturę ścieżek.
- Plik nowy jest kopiowany. Wcześniej skopiowany jest pomijany, gdy zgadzają się ścieżka, rozmiar w bajtach i modTime z tolerancją ±1 s.
- Zmieniony plik dostaje nową kopię; starsze wersje pozostają w historii.
- Po kopiowaniu program ustawia lokalny modTime i weryfikuje wynik.
- Opcjonalny limit umożliwia małe przebiegi testowe.
- Log opisuje operacje, zmiany i błędy.
- Nowe wymaganie użytkownika: skan telefonu i raport przyrostu bez kopiowania zawartości.

Jest to jednokierunkowe archiwizowanie przyrostowe. Folder pojedynczego uruchomienia zawiera tylko przyrost, a nie pełny stan telefonu. Do odtworzenia pełnego stanu potrzebna jest historia albo indeks wersji. Usuwanie lokalnych kopii w reakcji na usunięcie pliku z telefonu nie wynika z obecnych wymagań.

## 3. Elementy już zaimplementowane

- Oddzielne moduły konfiguracji, obsługi telefonu, operacji lokalnych i koordynacji.
- Walidacja podstawowych pól YAML.
- Indeks lokalnych plików wybierający najnowszą wersję ścieżki z historii.
- Porównanie rozmiaru i czasu, ustawianie lokalnego modTime i weryfikacja.
- Wspólny timestamp logu i folderu przebiegu.
- 45 metod testowych: konfiguracja 10, operacje lokalne 20, obsługa USB 9, integracja 5, E2E 1.

Sama obecność testów nie potwierdza sprawności rzeczywistego transferu z telefonu.

## 4. Problemy implementacji

| Problem | Skutek / uwaga |
|---|---|
| README i specyfikacja wskazują python main.py, ale main.py nie istnieje | Udokumentowane uruchomienie nie działa. |
| Brak parsera argumentów CLI w punkcie wejścia | Opisane argumenty konfiguracji i limitu nie są obsługiwane. |
| Detektor ADB odrzuca każdą linię zawierającą device | Odrzuca także prawidłowe wiersze urządzeń. |
| Skaner ADB wpisuje modtime: 0, a MTP pomija modTime | Podstawowe wymaganie dokładnych metadanych nie jest spełnione. |
| Kopiowanie zawsze wywołuje mtp-getfile, także dla ADB | Wykrywanie, skanowanie i transfer nie stanowią spójnego mechanizmu. |
| Błędy skanowania są zamieniane na pustą listę | Nieudany skan może wyglądać jak brak nowych plików. |
| Wynik kopiowania nie decyduje o końcowym sukcesie | Program może ogłosić sukces mimo błędów. |
| Nieudana kopia pozostaje pod docelową nazwą | Kolejny przebieg może uwzględnić niezweryfikowany plik w historii. |
| Limit jest stosowany po rekurencyjnym skanie skonfigurowanego źródła | Dla jednego dużego źródła limit 1 nadal oznacza skan całego drzewa tego źródła. |

### Miejsca w kodzie

- src/usb_handler.py: find_files_for_copying(), _scan_folder_adb(), _find_device_via_adb().
- src/file_manager.py: copy_file_from_phone(), build_existing_files_index().
- src/phone_sync.py: run(), _copy_and_verify_file(), blok punktu wejścia.

Błąd ADB potwierdzono izolowanym sprawdzeniem: dla przykładowego poprawnego wyniku adb devices zawierającego ABC123 i status device detektor zwrócił None.

W run() błędy kopii trafiają do listy, ale po zakończeniu pętli ustawiane jest success = True. Specyfikacja wymaga zakończenia z błędem po nieudanej weryfikacji. Zwracana wartość run() nie jest też wykorzystywana przez obecny punkt wejścia do ustalenia kodu wyjścia.

## 5. Wykorzystanie doświadczeń z PhoneAccess

Podstawą skanowania na Windows powinien zostać sprawdzony odczyt Shell COM z scan_phone.py:

- System.Size: dokładna liczba bajtów, bez parsowania wyświetlanego rozmiaru.
- System.DateModified: czas z sekundami i zachowaną informacją o strefie źródłowej.
- System.FileName: nazwa wraz z rozszerzeniem, z jawną obsługą braku właściwości.
- Iteracyjne przechodzenie drzewa bez arbitralnego limitu głębokości.
- Jawne błędy brakujących metadanych, bez zastępowania ich zerem.
- Zachowanie częściowego raportu po przerwaniu.
- Raport UTF-8, utrwalany w trakcie przebiegu, z informacją o kompletności.

Dokładność oznacza dokładność metadanych udostępnionych przez telefon/MTP. Nie należy obiecywać większej precyzji niż źródło rzeczywiście dostarcza. Nie wolno dopowiadać strefy czasowej, jeśli źródło jej nie udostępniło.

PhoneAccess potwierdza odczyt metadanych. Mechanizm kopiowania trzeba osobno zaimplementować i sprawdzić, w tym rozpoznawanie zakończenia transferu i obsługę odłączenia telefonu. Odczyt metadanych nie stanowi dowodu poprawnego transferu zawartości.

## 6. Spójność specyfikacji

Cel jest sensowny, ale docs/PhoneSync_Spec.md wymaga ujednolicenia:

- Opis max_files_per_sync mówi o pełnym skanie, a przebieg działania o natychmiastowym zatrzymaniu skanowania.
- Timestamp raz powstaje przy starcie, później w konfiguracji logowania.
- Zakaz przekazywania timestampu jako parametru jest zbędnym ograniczeniem implementacyjnym. Wymaganiem powinien być wspólny identyfikator przebiegu.
- Dokument mówi, że interfejs CLI/GUI nie jest określony, choć opisuje konkretne CLI.
- Najstarsze pliki najpierw nie określa, czy chodzi o cały telefon, czy pojedyncze katalogi.
- Wszystkie wcześniejsze kopie nie rozstrzyga porównania z dowolną historyczną wersją czy z najnowszą. Kod indeksuje najnowszą.

Rekomendacja: porównywać z najnowszą zweryfikowaną kopią danej ścieżki. Powrót telefonu do starszej wersji również będzie wtedy zmianą do archiwizacji.

## 7. Proponowany tryb skanowania bez kopiowania

Proponowane operacje (obecnie niezaimplementowane):

| Operacja | Wynik |
|---|---|
| inventory | Spis plików telefonu i ich metadanych. |
| plan | Lista przyrostu względem wcześniejszych kopii, bez transferu zawartości. |
| sync | Kopiowanie przyrostu według tych samych reguł porównywania. |

Dla potrzeby użytkownika najważniejsze jest plan. Raport powinien rozróżniać:

- NEW: brak wcześniejszej kopii tej ścieżki.
- CHANGED: najnowsza kopia ma inny rozmiar lub modTime.
- UNCHANGED: metadane się zgadzają.
- UNKNOWN: nie można wiarygodnie porównać.
- ERROR: błąd odczytu.

Summary: liczby plików w kategoriach, sumy bajtów NEW i CHANGED, błędy, czas przebiegu oraz informacja, czy skan był kompletny. Szczegółowy TSV UTF-8: ścieżka, rozmiar, modTime ze strefą, status i powód. Brakujące rozmiary nie powinny wchodzić do sum bajtów; liczba braków powinna być jawna.

Sam skan telefonu nie wystarcza, żeby stwierdzić jeszcze nie przegrane. Potrzebna jest baza porównawcza: lokalne kopie albo zapisany indeks udanych transferów. Można skanować tylko telefon jako źródło bieżących danych, korzystając z istniejącego indeksu historii. Indeks musi uwzględniać politykę dotyczącą kopii później usuniętych lub zmienionych na laptopie.

Plan nie aktualizuje historii udanych kopii i nie tworzy pustego folderu Sync_*. Zapis raportu lokalnego jest dozwolony. Inventory i plan są odrębnymi operacjami, ponieważ spis telefonu nie jest automatycznie listą przyrostu.

## 8. Wymagania do doprecyzowania

- Tożsamość telefonu: nazwa modelu nie wystarcza; dwa telefony mogą mieć identyczną nazwę.
- Tożsamość pamięci: ścieżka rozróżnia pamięć wewnętrzną i kartę SD.
- Zakres całego telefonu: wszystkie pamięci udostępnione przez MTP, bez obietnicy dostępu do prywatnych danych aplikacji.
- Brak metadanych: UNKNOWN, bez uznawania pliku za niezmieniony.
- Kompletność: osobne statusy pełnego skanu, przerwania, limitu i błędów.
- Limity: oddzielić limit kopiowania od wcześniejszego zatrzymania skanu. Pełne summary wymaga pełnego skanu.
- Kolejność: określić deterministyczną kolejność folderów i plików. Globalne sortowanie najstarszych wymaga zebrania całego zakresu i koliduje z szybkim zatrzymaniem skanu.
- Kopiowanie: plik tymczasowy, weryfikacja, dopiero potem docelowa nazwa i wpis do historii.
- Zmiany podczas transferu: ponowny odczyt metadanych źródła. Skan nie jest atomową migawką.
- Ścieżki Windows: obsługa kolizji wielkości liter, niedozwolonych nazw, zbyt długich ścieżek i bezpiecznego pozostawania wewnątrz katalogu docelowego.
- Weryfikacja: rozmiar i ustawiony modTime nie potwierdzają identyczności zawartości. Hash może stanowić opcjonalne, mocniejsze sprawdzenie.
- Status procesu: błędy skutkują odpowiednim kodem wyjścia i uczciwym summary.
- Kolizje przebiegów: identyfikator ma być unikalny; uruchomienia w tej samej sekundzie nie powinny współdzielić folderu ani nadpisywać logu.
- Przywracanie: jasno opisać, że foldery są przyrostami i jak wybrać najnowsze wersje przy odtwarzaniu.

## 9. Propozycja uporządkowania repozytorium

- Jeden pakiet src/phonesync/ i jeden działający punkt wejścia.
- Rozdzielenie skanowania, wyznaczania przyrostu i wykonywania kopii.
- Jeden podstawowy mechanizm Windows/MTP. ADB dopiero jako świadomie utrzymywana alternatywa.
- Usunięcie lub przeniesienie nieużywanych eksperymentów, w tym windows_mtp_detection.py.
- PhoneSync_config.example.yaml bez osobistej ścieżki użytkownika; lokalna konfiguracja osobno.
- pyproject.toml z zależnościami wykonawczymi i testowymi. Obecne pymtp nie jest używane przez kod, a pywin32 nie jest zadeklarowane.
- README: aktualna instalacja, działające komendy, ograniczenia i status projektu.
- Specyfikacja: wymagania. Dokument architektury: aktualny przepływ. Historia debugowania: osobno i wyraźnie jako historyczna.
- Testy lokalne izolowane w katalogach tymczasowych. Testy z telefonem uruchamiane świadomie i osobno.

Dokument debugging_mtp_device_detection.md ogłasza rozwiązanie problemu przez test z atrapą, podczas gdy obecny test E2E wymaga prawdziwego telefonu. Opisana historyczna próba nie potwierdza naprawy rzeczywistego dostępu MTP. Dokument przepływu także odwołuje się do nieistniejącego main.py i nieaktualnych metod.

## 10. Ocena testów

- Obecny test E2E dopuszcza files_copied == 0 i nie wymaga pustej listy błędów, więc nie potwierdza udanego transferu.
- Testy limitu zastępują skaner własną symulacją, więc nie potwierdzają zatrzymania rzeczywistego skanowania.
- Testy integracyjne zapisują do c:/Users/Wojtek/PhoneSync i zostawiają artefakty; wyniki zależą od osobistego środowiska i historii przebiegów.
- Część testów tworzy foldery w tej samej sekundzie, więc może sprawdzać tę samą lokalizację zamiast dwóch wersji historii.
- Pełna suite nie została uruchomiona w trakcie tej oceny.

W dalszych pracach potrzebne są testy rzeczywistych reguł porównania, błędów i kompletności skanu, rozróżniania pamięci/urządzeń, historii zweryfikowanych kopii oraz obsługi nieudanego transferu. Test sprzętowy powinien potwierdzić co najmniej jedną udaną kopię, poprawne metadane i pominięcie jej w kolejnym przebiegu w kontrolowanym scenariuszu.

## 11. Rekomendowana kolejność prac

1. Ujednolicić wymagania dotyczące limitów, wersji historycznych i statusów.
2. Wprowadzić sprawdzone skanowanie metadanych z PhoneAccess.
3. Dodać inventory i plan, realizując potrzebę raportu przyrostu bez kopiowania.
4. Naprawić kopiowanie, weryfikację i propagację błędów.
5. Oddzielić testy lokalne od testów wymagających telefonu i osobistego archiwum.
6. Uporządkować pakiet, zależności i dokumentację.

Najpierw warto zbudować wiarygodny raport przyrostu. Pozwoli zobaczyć, co czeka na przegranie, i sprawdzić reguły porównywania przed wykonywaniem transferów.