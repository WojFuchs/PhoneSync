# PhoneSync

Automatyczne kopiowanie plików z telefonu Android (USB/MTP) na laptop z Windows 10.

## Funkcje

- Skanowanie telefonu Android podłączonego przez USB w trybie MTP
- Kopiowanie plików inkrementalne ze wskazanych folderów
- Automatyczne zachowywanie struktury folderów
- Weryfikacja plików po kopiowaniu (rozmiar + czas modyfikacji)
- Konfiguracja przez plik YAML
- Szczegółowe logowanie operacji

## Wymagania

- Windows 10
- Python 3.8+
- Telefon Android podłączony przez USB w trybie File Transfer (MTP)

## Instalacja

```bash
pip install -r requirements.txt
```

## Konfiguracja

Edytuj `PhoneSync_config.yaml`:

```yaml
phone_folders:
  - Pictures
  - Documents

destination_folder: "c:\\Users\\Twoja_nazwa\\PhoneSync"

excluded_folders:
  - .thumbnails
  - .cache
```

## Uruchomienie

```bash
python main.py
```

Program stworzy folder `Sync_<timestamp>_<Phone_Name>` w folderze docelowym i skopiuje pliki.

## Logika inkrementalna

- Jeśli plik istnieje i rozmiar + modTime się zgadzają → pominięty
- Jeśli plik się zmienił na telefonie → skopiowany ponownie do najnowszego folderu z WARNING
- Jeśli plik nowy → skopiowany

## Testowanie

```bash
python -m pytest tests/
```

## Specification

Pełna specyfikacja dostępna w [docs/PhoneSync_Spec.md](docs/PhoneSync_Spec.md)
