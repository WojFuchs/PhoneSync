---
name: python-phonesync-english
description: "Use when: writing Python code for PhoneSync project. Principle: all variable names, comments, and log messages must be in English."
---

# Python PhoneSync - English Language

Wszystkie nazwy zmiennych, komentarze, i wiadomości logowania w kodzie muszą być po angielsku. To zapewnia spójność i zrozumiałość kodu dla międzynarodowych zespołów.

## Obowiązuje
- ✓ Nazwy zmiennych, funkcji, klas
- ✓ Komentarze i dokumentacja
- ✓ Komunikaty logowania i błędów
- ✓ Komunikaty dla użytkownika

## Przykład
```python
# ✓ Correct
files_changed = []  # Track modified files
logger.warning(f"File changed on phone: {file_path}")

# ✗ Wrong
zmienione_pliki = []  # Śledzenie zmienionych plików
logger.warning(f"Plik się zmienił na telefonie: {file_path}")
```
