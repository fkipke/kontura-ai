"""Regex-basierter PIIMasker fuer DACH-Buchhaltung.

Erkennt strukturierte PII (IBAN, USt-IdNr, E-Mail, Telefon, Kreditkarten) und
ersetzt sie durch sprechende Platzhalter wie '[IBAN_1]', '[EMAIL_2]'.

Das Mapping wird zurueckgegeben, sodass eine LLM-Antwort optional re-substituted
werden kann (z.B. wenn das Modell den Platzhalter zurueckschreibt).
"""

from collections import defaultdict

from kontura.ai.pii.base import MaskedText, PIIEntity
from kontura.ai.pii.patterns import MASKING_ORDER


class RegexMasker:
    """Default-Implementation des PIIMasker-Protocols.

    Iteriert die Pattern-Liste in definierter Reihenfolge (spezifisch -> generisch)
    und ersetzt Treffer durch eindeutige Platzhalter.
    """

    def mask(self, text: str) -> MaskedText:
        if not text:
            return MaskedText(masked_text=text, entities=[])

        masked = text
        entities: list[PIIEntity] = []
        # Pro Entity-Typ einen eigenen Counter, damit Platzhalter sprechend bleiben.
        counters: dict[str, int] = defaultdict(int)
        # Cache: gleicher Originalwert -> gleicher Platzhalter (Konsistenz im Text).
        seen: dict[tuple[str, str], str] = {}

        for entity_type, pattern in MASKING_ORDER:
            # findall waere nicht reihenfolgesicher; finditer schon.
            # Wir bauen eine Liste der Treffer und ersetzen Sie ANSCHLIESSEND
            # rueckwaerts (verhindert Index-Verschiebungen).
            matches = list(pattern.finditer(masked))
            if not matches:
                continue

            # Rueckwaerts ersetzen, damit start/end-Indizes der vorhergehenden
            # Treffer gueltig bleiben.
            for match in reversed(matches):
                original = match.group(0)
                cache_key = (entity_type, original)
                if cache_key in seen:
                    placeholder = seen[cache_key]
                else:
                    counters[entity_type] += 1
                    placeholder = f"[{entity_type}_{counters[entity_type]}]"
                    seen[cache_key] = placeholder
                    entities.append(
                        PIIEntity(
                            entity_type=entity_type,
                            placeholder=placeholder,
                            original_value=original,
                        )
                    )

                masked = masked[: match.start()] + placeholder + masked[match.end() :]

        # Reihenfolge der Entities umkehren, damit "_1" wirklich vor "_2" kommt.
        entities.reverse()

        return MaskedText(masked_text=masked, entities=entities)
