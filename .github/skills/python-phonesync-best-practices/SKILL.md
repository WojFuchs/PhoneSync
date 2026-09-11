---
name: python-phonesync-best-practices
description: "Use when: writing Python code for PhoneSync project. Principle: avoid one-off functions with 1-2 lines called only once - inline the code instead."
---

# Python PhoneSync Best Practices

**Nie tworzyć funkcji z 1-2 linijkami kodu, które są wywołane tylko raz.** Wbuduj logikę bezpośrednio.

## ✗ Źle
```python
def get_ext(f):
    return f.split('.')[-1]

ext = get_ext(file)  # tylko raz w kodzie
```

## ✓ Dobrze
```python
ext = file.split('.')[-1]  # bezpośrednio
```

**Wyjątek:** Funkcja z 1-2 linijkami jest OK jeśli wywoływana wielokrotnie lub stanowi ważną abstrakcję (np. `normalize_phone_name()`).
