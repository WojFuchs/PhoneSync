---
name: python-phonesync-simplicity
description: "Use when: writing Python code for PhoneSync project. Principle: avoid unnecessary classes and abstractions. Keep code simple and readable."
---

# Python PhoneSync - Simplicity over Abstraction

Nie tworzyć klas ani obiektów dla prostych operacji, które mogą być wykonane w kilka linijek. Funkcja lub kilka linijek kodu wbudowanego w logikę programu jest lepsze niż abstrakcja, która jest używana tylko raz.

## Zasada
- **Klasa z 10 linijkami kodu uzyta tylko raz** → Złe
- **Proste operacje wbudowane w logikę** → Dobre
- **Wielokrotnie używane abstrakcje** → OK, warto wyodrębnić

Kod powinien być prosty do czytania i zrozumienia, bez zbędnych warstw abstrakcji.
