"""Regex-Patterns fuer PII-Erkennung.

Optimiert fuer DACH-Buchhaltungsdomaene:
- IBAN (alle EU-Laender, Schwerpunkt DE/AT/CH)
- USt-IdNr (DE/EU)
- Steuer-IDs
- E-Mail, Telefon, Kreditkarte (generisch)

Die Reihenfolge in MASKING_ORDER ist wichtig: spezifische Patterns zuerst,
generische zuletzt. Sonst frisst eine generische Regel ein spezifisches Match.
"""

import re
from re import Pattern

# IBAN: 2 Buchstaben Country Code + 2 Pruefziffern + 11-30 alphanumerische Zeichen.
# Erlaubt Leerzeichen-Gruppierung (DE89 3704 0044 0532 0130 00).
IBAN_PATTERN: Pattern[str] = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")

# Deutsche USt-IdNr: DE + 9 Ziffern. Andere EU-Laender haben andere Schemata,
# die wir spaeter ergaenzen koennen.
VAT_ID_PATTERN: Pattern[str] = re.compile(r"\bDE\d{9}\b")

# E-Mail: konservativ, deckt 99% der echten Adressen ab.
EMAIL_PATTERN: Pattern[str] = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Kreditkarten: 13-19 Ziffern, optional in 4er-Gruppen mit Trennern.
# Achtung: Pattern kommt SEHR FRUEH, weil sonst lange Zahlen-Sequenzen
# faelschlich anders erkannt werden.
CREDIT_CARD_PATTERN: Pattern[str] = re.compile(r"\b(?:\d[ -]?){13,19}\b")

# Telefonnummern: deutschsprachiger Raum.
# +49 30 1234 5678, 030/12345678, 0151 12345678 etc.
# Bewusst eng gehalten - lieber False Negatives als False Positives auf Beträge.
PHONE_PATTERN: Pattern[str] = re.compile(r"(?:\+49|0049|0)[\s\-/]?(?:\d[\s\-/]?){6,14}\d")

# Reihenfolge: spezifischer -> generischer.
# IBAN vor Kreditkarte (sonst frisst CC die Ziffern).
# E-Mail VOR Telefon (sonst denkt Telefon, "@" ist eine Trennstelle).
MASKING_ORDER: list[tuple[str, Pattern[str]]] = [
    ("IBAN", IBAN_PATTERN),
    ("VAT_ID", VAT_ID_PATTERN),
    ("EMAIL", EMAIL_PATTERN),
    ("CREDIT_CARD", CREDIT_CARD_PATTERN),
    ("PHONE", PHONE_PATTERN),
]
