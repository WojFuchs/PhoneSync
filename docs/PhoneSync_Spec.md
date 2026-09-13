# PhoneSync - Specyfikacja Programu

## Opis Ogólny
**PhoneSync** to program do automatycznego kopiowania plików z telefonu Android podłączonego kablem USB do laptopa z systemem Windows 10.

## Główny Cel
Umożliwić szybkie i automatyczne pobieranie plików z wybranych folderów na telefonie Android na dysk laptopa, bez konieczności ręcznego zarządzania poszczególnymi plikami.

## Wymagania Techniczne

### Środowisko
- **System operacyjny:** Windows 10
- **Urządzenie Android:** Podłączone kablem USB w trybie **File Transfer** (MTP)
- **Połączenie:** USB z aktywnym trybem transferu plików

### Architektura
Program powinien pracować w środowisku Windows i współpracować z systemem plików telefonu dostępnym przez USB (MTP).

## Główne Funkcje

### 1. Konfiguracja
- Plik konfiguracyjny w formacie **YAML**: `PhoneSync_config.yaml`
- Zawiera:
  - **Lista folderów źródłowych** na telefonie do przeszukiwania (recursively)
  - **Folder docelowy** na laptopie
  - **Lista folderów do wykluczenia** (np. `.thumbnails`)
  
- **Domyślna konfiguracja:**
  - Foldery źródłowe: `Pictures`
  - Folder docelowy: `c:\Users\Wojtek\PhoneSync\`
  - Foldery wykluczone: `.thumbnails`

### 2. Skanowanie i Kopiowanie Inkrementalne
- Program ma:
  - Znaleźć telefon podłączony przez USB
  - Przeszukać wskazane foldery na telefonie **recursively** (ze wszystkich podfolderów)
  - Pominąć foldery wskazane na liście wykluczeń
  - Kopiować **inkrementalnie** z następującą logiką:
    - Sprawdzić pliki ze **wszystkich istniejących folderów `Sync_*_<Phone_Name>`**
    - Jeśli plik o identycznej ścieżce i nazwie już istnieje:
      - Porównać **rozmiar** i **modTime** z telefonem
      - Jeśli rozmiar i modTime się zgadzają (modTime może się różnić o max. 1 sekundę) → plik już skopiowany, pominąć
      - Jeśli rozmiar LUB modTime się różnią → **WARNING**: "Plik się zmienił na telefonie: [ścieżka/nazwa]", skopiować do najnowszego folderu `Sync_*_<Phone_Name>`
      - Jeśli plik nie istnieje w żadnym `Sync_*_<Phone_Name>` → skopiować do najnowszego folderu `Sync_*_<Phone_Name>`

### 3. Struktura Docelowa
- Przy każdym uruchomieniu program tworzy **nowy subfolder** w postaci `Sync_<timestamp>_<Phone_Name>` w folderze docelowym
- **Pełne ścieżki są zachowywane**: struktura folderów na telefonie jest odtworzona w `Sync_<timestamp>_<Phone_Name>/`
- Przykład:
  - Na telefonie: `/Pictures/Vacation/photo1.jpg`
  - Na laptopie: `c:\Users\Wojtek\PhoneSync\Sync_20260909_143022_SM_A515F\Pictures\Vacation\photo1.jpg`

### 4. Obsługa Metadanych Plików
- **Rozmiar pliku**: Odczyt rozmiaru w bajtach z telefonu
- **Weryfikacja**: Po skopiowaniu sprawdzenie, czy rozmiar na laptopie zgadza się z originalem z dokładnością do bajtu
- **Modification Time (modTime)**:
  - Odczyt dokładnego czasu modyfikacji z telefonu (do sekundy)
  - Telefon pozostaje **read-only** - nic nie modyfikujemy na telefonie
  - Po skopiowaniu na laptopa: automatyczne ustawienie modTime na laptopie do wartości odczytanej z telefonu
  - Zachowanie dokładności do sekundy
  
### 4a. Logika Porównywania Plików (Inkrementalne Kopiowanie)
- Plik uznawany za **już wcześniej skopiowany** jeśli:
  - Ścieżka i nazwa pliku są identyczne
  - **Rozmiar** zgadza się dokładnie (w bajtach)
  - **modTime** zgadza się z tolerancją **±1 sekunda**
  
- Plik wymaga **nowego kopiowania** jeśli:
  - Istnieje w `Sync_*_<Phone_Name>` z tym samym path/nazwa ale **rozmiar się różni** LUB **modTime się różni o więcej niż 1 sekundę**
  - Wyświetlić **WARNING**: `"Plik się zmienił na telefonie: [relative_path/nazwa_pliku]"`
  - Skopiować go do **najnowszego folderu `Sync_*_<Phone_Name>`** (z najnowszym timestamp'em)

### 5. Bezpieczeństwo i Integracja USB
- Telefon traktowany jako **read-only** - żadne operacje zapisu
- Obsługa USB/MTP - przy braku wsparcia dla konkretnego wymagania szukać alternatywnych rozwiązań
- Obsługa ścieżek relatywnych i bezwzględnych

## Plik Konfiguracyjny

### Lokalizacja
Nazwa: `PhoneSync_config.yaml` (w głównym folderze programu)

### Zawartość (przykład)
```yaml
phone_folders:
  - Pictures

destination_folder: "c:\\Users\\Wojtek\\PhoneSync"

excluded_folders:
  - .thumbnails
```

### Opis pól
- **phone_folders** (opcjonalny): Lista folderów na telefonie do przeszukiwania (rekursywnie ze wszystkich podfolderów). Jeśli brakuje lub jest pusta - program skanuje cały telefon (/) z wyłączeniem folderów z `excluded_folders`.
- **destination_folder**: Folder docelowy na laptopie
- **excluded_folders** (opcjonalny): Lista podfolderów do pominięcia (nie będą przeszukiwane ani kopiowane)
- **max_files_per_sync** (opcjonalny): Maksymalna liczba plików **do skopiowania** w jednym uruchomieniu. Jeśli nie ustawiono (null), program skopiuje wszystkie pliki wymagające inkrementalnego kopiowania. **Ważne**: limit dotyczy tylko plików faktycznie skopiowanych (już istniejących lub zmienionych), nie liczby skanowanych plików. Program skanuje wszystkie pliki, aby sprawdzić co się zmieniło, ale kopiuje tylko tych N. Można także przekazać ten parametr przez linię poleceń (ma priorytet nad konfiguracją).

## Przebieg Działania
1. Program odczytuje plik konfiguracyjny `PhoneSync_config.yaml` (oraz opcjonalnie pobiera `max_files_per_sync` z linii poleceń)
2. Szuka telefonu podłączonego przez USB
   - Znajduje nazwę telefonu z systemu Android
   - Normalizuje nazwę: zamienia wszystkie znaki nie-litery i nie-cyfry na `_`, usuwa powtarzające się `_`, trimuje `_` z obu końców
   - Przygotowuje znormalizowaną nazwę do użycia w nazwie folderu
3. Tworzy nowy subfolder `Sync_<timestamp>_<Phone_Name>` w folderze docelowym
4. **Skanuje foldery na telefonie folder po folderze z wbudowanym limitowaniem**:
   - Jeśli `phone_folders` jest pusta/pominięta → skanuje cały telefon od root (`/`)
   - Pomija foldery wymienione w `excluded_folders`
   - **W każdym folderze indywidualnie sortuje pliki po modTime** (od najstarszych do najnowszych)
5. **Podczas skanowania każdego folderu**: dla każdego pliku (w porządku sortowania):
   - **Natychmiast sprawdza czy plik się kwalifikuje do inkrementalnego kopiowania**:
     - Jeśli plik **już istnieje i nie zmienił się** → pominąć (skip)
     - Jeśli plik **już istnieje ale zmienił się** (rozmiar lub modTime) → dodać do listy do kopii
     - Jeśli plik **nie istnieje** → dodać do listy do kopii
6. **Przerwanie skanowania na limicie**:
   - Jeśli `max_files_per_sync` jest ustawiony → program zbiera pliki do kopii podczas skanowania
   - Gdy liczba plików do kopii osiągnie limit → **Program natychmiast przerywa skanowanie pozostałych folderów**
   - Loguje ile plików do kopii zebrano i co pozostało nieskanowane
   - **To znacznie oszczędza czas testowania** - nie skanuje całego telefonu
7. Dla każdego pliku z listy do skopiowania:
   - Odczytuje rozmiar pliku i modTime z telefonu
   - Kopiuje plik zachowując pełną ścieżkę (tworzy strukturę folderów w najnowszym `Sync_<timestamp>_<Phone_Name>/`)
   - Po skopiowaniu ustawia modTime na laptopie do wartości odczytanej z telefonu
   - **Weryfikuje rozmiar i modTime**: porównuje wartości na laptopie z wartościami na telefonie (rozmiar musi się zgadzać dokładnie, modTime ±1 sekunda)
   - Jeśli weryfikacja się nie powiedzie → program się kończy z błędem: `"BŁĄD: Weryfikacja pliku [path/nazwa] nie powiodła się - rozmiar lub modTime się nie zgadzają"`
8. Raportuje postęp operacji, wszystkie WARNING'i i ewentualne błędy

## Uruchamianie Programu

### Składnia
```bash
python main.py [config_path] [max_files_per_sync]
```

### Parametry
- `config_path` (opcjonalny): ścieżka do pliku konfiguracyjnego (domyślnie: `PhoneSync_config.yaml`)
- `max_files_per_sync` (opcjonalny): limit liczby plików do skopiowania (overriduje wartość z konfigu). **Ważne**: program skanuje foldery sekwencyjnie i przerwie skanowanie gdy osiągnie limit, co oszczędza czas na niepotrzebnym skanowaniu pozostałych folderów.

### Przykłady
```bash
# Uruchomienie z konfigu
python main.py

# Uruchomienie z innym plikiem konfigu
python main.py config_prod.yaml

# Uruchomienie z limitem 5 plików (overriduje konfigurację)
python main.py PhoneSync_config.yaml 5
```

## Testowanie

### Bezpieczne Testowanie Kopii Inkrementalnych z Prawdziwym Telefonem

**Kluczowy parameter do testowania: `max_files_per_sync` (w konfiguracji lub linii poleceń)**

- **Rekomendowana strategia testowania:**
  1. Zacząć z bardzo małym limitem przez linię poleceń: `python main.py PhoneSync_config.yaml 3`
  2. Uruchomić program i potwierdzić że zadziałało - zostały skopiowane dokładnie 3 pliki do skopiowania
  3. Po każdej iteracji zwiększać limit: `python main.py PhoneSync_config.yaml 5`, potem `10`, itd.
  4. Dopiero po potwierdzeniu że logika działa - uruchomić bez limitu: `python main.py` (skopiuje wszystkie)

- **Ważne: Program przerywa skanowanie PODCZAS skanowania**
  - Program skanuje telefon folder po folderze
  - Dla każdego pliku sprawdza czy się kwalifikuje do kopii (inkrementalne sprawdzenie)
  - Gdy osiągnie limit plików do skopiowania - **program natychmiast przerywa skanowanie pozostałych folderów**
  - Loguje informacje:
    - `"Reached copy limit during scan: X files collected"` 
  - To jest **bardzo ważne** dla wydajności testów - nie skanuje całego telefonu!
  - W następnym uruchomieniu z limitem będzie skanować od nowa i zbierze kolejne pliki

- **Co weryfikować podczas testowania:**
  - Czy pliki zostały skopiowane do prawidłowego folderu `Sync_<timestamp>_<Phone_Name>/`
  - Czy **rozmiar pliku** na laptopie **dokładnie zgadza się** z rozmiarem na telefonie (do bajtu)
  - Czy **modTime (czas modyfikacji)** na laptopie zgadza się z czasem na telefonie (tolerancja ±1 sekunda)
  - Czy struktura folderów jest prawidłowo zachowana
  - Czy logika inkrementalna działa - w następnym uruchomieniu już skopiowane pliki są pomijane
  - Czy pliki które się zmieniły na telefonie są ponownie skopiowane z WARNING'iem
  - Czy log pokazuje że program wczesnie przerwał skanowanie (jeśli było co skanować dalej)

- **Scenariusze testowe**:
  1. **Pierwsze uruchomienie z limitem**: Skopiować 3-5 plików, sprawdzić czy się prawidłowo skopiowały. Log powinien pokazać `"Reached copy limit during scan"`.
  2. **Drugie uruchomienie z tym samym limitem**: Sprawdzić że poprzednie pliki są pomijane ("already synced"). Powinny zostać skopiowane kolejne 3-5 plików.
  3. **Zmiana pliku na telefonie**: Zmienić jeden z już skopiowanych plików, uruchomić program - powinien pokazać WARNING i skopiować zmieniony plik
  4. **Pełne kopiowanie**: Po potwierdzeniu logiki - uruchomić bez limitu

### Strategia Testowania Bez Limitu
- Dopiero po potwierdzeniu prawidłowego działania na małych liczbach plików
- Można przystąpić do pełnego kopiowania całej zawartości telefonu
- Zarejestrować czas działania dla potrzeb optymalizacji jeśli zajdzie potrzeba

## Uwagi Dodatkowe

### Technologia i Integracja
- Pierwotnie preferowane: MTP (Media Transfer Protocol)
- Jeśli któreś z wymagań nie są osiągalne z MTP, szukać alternatywnych rozwiązań
- Program powinien być niezawodny i obsługiwać ewentualne błędy komunikacji USB

### Wymagania Non-Functional
- Program powinien działać na Windows 10
- Na tym etapie specyfikacji nie ma wymagań dotyczących interfejsu użytkownika (CLI czy GUI)
- Telefon musi pozostać read-only - żadne operacje zapisu na telefonie
- Dokładność czasu modyfikacji plików do sekundy

---
**Data utworzenia:** 2026-09-09  
**Status:** Specyfikacja wstępna
