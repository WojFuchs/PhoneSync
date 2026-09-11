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
    - Sprawdzić pliki ze **wszystkich istniejących folderów `Sync_*`**
    - Jeśli plik o identycznej ścieżce i nazwie już istnieje:
      - Porównać **rozmiar** i **modTime** z telefonem
      - Jeśli rozmiar i modTime się zgadzają (modTime może się różnić o max. 1 sekundę) → plik już skopiowany, pominąć
      - Jeśli rozmiar LUB modTime się różnią → **WARNING**: "Plik się zmienił na telefonie: [ścieżka/nazwa]", skopiować do najnowszego folderu `Sync_*`
      - Jeśli plik nie istnieje w żadnym `Sync_*` → skopiować do najnowszego folderu `Sync_*`

### 3. Struktura Docelowa
- Przy każdym uruchomieniu program tworzy **nowy subfolder** w postaci `Sync_<timestamp>` w folderze docelowym
- **Pełne ścieżki są zachowywane**: struktura folderów na telefonie jest odtworzona w `Sync_<timestamp>/`
- Przykład:
  - Na telefonie: `/Pictures/Vacation/photo1.jpg`
  - Na laptopie: `c:\Users\Wojtek\PhoneSync\Sync_20260909_143022\Pictures\Vacation\photo1.jpg`

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
  - Istnieje w `Sync_*` z tym samym path/nazwa ale **rozmiar się różni** LUB **modTime się różni o więcej niż 1 sekundę**
  - Wyświetlić **WARNING**: `"Plik się zmienił na telefonie: [relative_path/nazwa_pliku]"`
  - Skopiować go do **najnowszego folderu `Sync_*`** (z najnowszym timestamp'em)

### 5. Bezpieczeństwo i Integracja USB
- Telefon traktowany jako **read-only** - żadne operacje zapisu
- Obsługa USB/MTP - przy braku wsparcia dla konkretnego wymagania szukać alternatywnych rozwiązań
- Obsługa ścieżek relatywnych i bezwzględnych

## ⚙️ Plik Konfiguracyjny

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
- **phone_folders**: Lista folderów na telefonie do przeszukiwania (rekursywnie ze wszystkich podfolderów)
- **destination_folder**: Folder docelowy na laptopie
- **excluded_folders**: Lista podfolderów do pominięcia (nie będą przeszukiwane ani kopiowane)

## Przebieg Działania
1. Program odczytuje plik konfiguracyjny `PhoneSync_config.yaml`
2. Tworzy nowy subfolder `Sync_<timestamp>` w folderze docelowym
3. Szuka telefonu podłączonego przez USB
4. Przeszukuje foldery wskazane w konfiguracji **recursively** (ze wszystkich podfolderów)
5. Dla każdego znalezionego pliku:
   - Sprawdza czy plik o identycznej ścieżce i nazwie istnieje w którymkolwiek z istniejących folderów `Sync_*`
   - Jeśli **istnieje**:
     - Porównuje rozmiar i modTime
     - Jeśli rozmiar i modTime się zgadzają (modTime ±1 sekunda) → pominąć (już skopiowany)
     - Jeśli rozmiar lub modTime się różnią → wyświetlić WARNING i skopiować do najnowszego `Sync_*`
   - Jeśli **nie istnieje** w żadnym `Sync_*`:
     - Odczytuje rozmiar pliku i modTime z telefonu
     - Kopiuje plik zachowując pełną ścieżkę (tworzy strukturę folderów w najnowszym `Sync_<timestamp>/`)
     - Po skopiowaniu ustawia modTime na laptopie do wartości odczytanej z telefonu
     - Weryfikuje rozmiar pliku (musi się zgadzać dokładnie)
6. Raportuje postęp operacji, wszystkie WARNING'i i ewentualne błędy

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

### Przyszłe Rozszerzenia
- Brak wymagań dotyczących synchronizacji dwukierunkowej
- Brak wymagań dotyczących usuwania duplikatów
- Brak wymagań dotyczących kompresji czy transformacji plików

---
**Data utworzenia:** 2026-09-09  
**Status:** Specyfikacja wstępna
