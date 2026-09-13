# PhoneSync - Przepływ Sterowania

## Hierarchia Wywołań

```
📄 main.py
│
└──→ 📄 phone_sync.py → 🔵 main()    
    │ *Punkt wejścia, inicjalizuje PhoneSync i uruchamia proces*
    │
    ├──→ 🟣 PhoneSync → 🔵 __init__()    
    │   │ *Inicjalizacja orchestratora*
    │   │
    │   ├──→ 📄 config.py → 🔵 load_config()    
    │   │ *Ładuje plik PhoneSync_config.yaml*
    │   │
    │   ├──→ 📄 config.py → 🔵 validate_config()    
    │   │ *Sprawdza poprawność struktury konfiguracji*
    │   │
    │   └──→ 📄 file_manager.py → 🟣 LocalFileManager → 🔵 __init__()    
    │       *Inicjalizuje menedżer operacji na dysku*
    │
    └──→ 🟣 PhoneSync → 🔵 run()    
        │ *Główna logika synchronizacji*
        │
        ├──→ 📄 usb_handler.py → 🔵 find_connected_device()    
        │   │ *Wyszukuje urządzenie Android podłączone przez USB*
        │   │
        │   └──→ 📄 usb_handler.py → 🟣 AndroidDevice → 🔵 __init__()    
        │       *Tworzy obiekt reprezentujący urządzenie*
        │
        ├──→ 📄 usb_handler.py → 🟣 USBScanner → 🔵 __init__()    
        │   │ *Inicjalizuje skaner do przeszukiwania telefonu*
        │
        ├──→ 🟣 USBScanner → 🔵 find_all_files()    
        │   │ *Wyszukuje wszystkie pliki na telefonie*
        │   │
        │   └──→ 🟣 USBScanner → 🔵 _scan_folder_recursive()    
        │       *Rekurencyjnie przeszukuje foldery i zbiera metadane*
        │
        ├──→ 📄 file_manager.py → 🟣 LocalFileManager → 🔵 create_sync_folder()    
        │   │ *Tworzy nowy folder Sync_<timestamp>_<phone_name>*
        │
        ├──→ 🟣 LocalFileManager → 🔵 find_existing_sync_folders()    
        │   │ *Wyszukuje istniejące foldery Sync do porównania*
        │
        └──→ 🟣 PhoneSync → 🔵 _process_file() [PĘTLA]    
            │ *Przetwarzanie każdego pliku znalezionego na telefonie*
            │
            ├──→ 🟣 LocalFileManager → 🔵 find_file_in_sync_folders()    
            │   │ *Sprawdza czy plik już istnieje w starszych folderach Sync*
            │
            ├──→ 🟣 LocalFileManager → 🔵 is_file_unchanged()    
            │   │ *Porównuje rozmiar i czas modyfikacji z telefonu*
            │
            └──→ 🟣 PhoneSync → 🔵 _copy_and_verify_file()    
                │ *Kopiuje plik z telefonu, ustawia czas i weryfikuje*
                │
                ├──→ 📄 file_manager.py → 🟣 LocalFileManager → 🔵 copy_file_from_phone()    
                │   │ *Kopiuje plik z telefonu na laptop używając MTP*
                │
                ├──→ 🟣 LocalFileManager → 🔵 set_file_modtime()    
                │   │ *Ustawia czas modyfikacji skopiowanego pliku*
                │
                └──→ 🟣 LocalFileManager → 🔵 verify_copied_file()    
                    *Weryfikuje rozmiar i czas modyfikacji skopiowanego pliku*
```

**Legenda:**
- 📄 = Pliki (`.py`)
- 🟣 = Klasy
- 🔵 = Funkcje/Metody
- *Italika* = Opis co robi
