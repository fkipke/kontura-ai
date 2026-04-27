"""Tests fuer den PII-Masker.

Wichtigster Test-Layer im Projekt: Wenn hier Bugs sind, gehen Customer-Daten
ungeschuetzt zu OpenAI. Daher: hohe Coverage, viele Edge-Cases.
"""

from kontura.ai.pii import PIIMasker, RegexMasker


def test_regex_masker_implements_protocol() -> None:
    """RegexMasker muss strukturell PIIMasker erfuellen."""
    masker = RegexMasker()
    assert isinstance(masker, PIIMasker)


def test_mask_empty_text_returns_empty() -> None:
    """Leerer Text bleibt leer, ohne Crash."""
    masker = RegexMasker()
    result = masker.mask("")
    assert result.masked_text == ""
    assert result.entities == []


def test_mask_text_without_pii_unchanged() -> None:
    """Text ohne PII darf nicht modifiziert werden."""
    masker = RegexMasker()
    text = "Rechnung Nr. 12345 vom 1.5.2026 ueber 199 EUR"
    result = masker.mask(text)
    assert result.masked_text == text
    assert result.entities == []


def test_mask_iban_replaces_with_placeholder() -> None:
    """Eine IBAN wird durch [IBAN_1] ersetzt."""
    masker = RegexMasker()
    result = masker.mask("Bitte zahlen auf DE89370400440532013000.")
    assert "[IBAN_1]" in result.masked_text
    assert "DE89370400440532013000" not in result.masked_text
    assert len(result.entities) == 1
    assert result.entities[0].entity_type == "IBAN"
    assert result.entities[0].original_value == "DE89370400440532013000"


def test_mask_iban_with_spaces_works() -> None:
    """IBAN mit Leerzeichen-Gruppierung wird auch erkannt."""
    masker = RegexMasker()
    result = masker.mask("IBAN: DE89 3704 0044 0532 0130 00")
    assert "[IBAN_1]" in result.masked_text


def test_mask_email_replaces() -> None:
    """E-Mail-Adresse wird maskiert."""
    masker = RegexMasker()
    result = masker.mask("Kontakt: rechnung@beispiel-firma.de")
    assert "[EMAIL_1]" in result.masked_text
    assert "rechnung@beispiel-firma.de" not in result.masked_text


def test_mask_vat_id_replaces() -> None:
    """Deutsche USt-IdNr (DE + 9 Ziffern) wird erkannt."""
    masker = RegexMasker()
    result = masker.mask("USt-IdNr: DE123456789")
    assert "[VAT_ID_1]" in result.masked_text


def test_mask_multiple_distinct_entities_get_unique_placeholders() -> None:
    """Zwei verschiedene IBANs -> [IBAN_1] und [IBAN_2]."""
    masker = RegexMasker()
    result = masker.mask("Konto 1: DE89370400440532013000, Konto 2: DE12345678901234567890")
    assert "[IBAN_1]" in result.masked_text
    assert "[IBAN_2]" in result.masked_text
    assert len(result.entities) == 2


def test_mask_same_entity_twice_gets_same_placeholder() -> None:
    """Selber Wert kommt 2x vor -> selber Platzhalter (Konsistenz)."""
    masker = RegexMasker()
    iban = "DE89370400440532013000"
    text = f"Erste Erwaehnung: {iban}. Zweite: {iban}."
    result = masker.mask(text)
    # Beide Vorkommen muessen denselben Platzhalter haben.
    assert result.masked_text.count("[IBAN_1]") == 2
    assert result.masked_text.count("[IBAN_2]") == 0


def test_mask_mixed_pii_in_realistic_invoice() -> None:
    """Realistischer Rechnungstext mit IBAN + USt-IdNr + E-Mail."""
    masker = RegexMasker()
    text = (
        "Lieferant ACME GmbH, USt-IdNr DE123456789, "
        "Kontakt rechnung@acme.de, "
        "Bankverbindung IBAN DE89370400440532013000."
    )
    result = masker.mask(text)
    # Alle drei muessen weg sein.
    assert "DE123456789" not in result.masked_text
    assert "rechnung@acme.de" not in result.masked_text
    assert "DE89370400440532013000" not in result.masked_text
    # Drei distinct Entities.
    assert len(result.entities) == 3


def test_unmask_restores_original_values() -> None:
    """unmask() ersetzt Platzhalter wieder durch Originalwerte."""
    masker = RegexMasker()
    masked = masker.mask("Kontakt: ich@example.com, IBAN DE89370400440532013000")
    # LLM koennte etwas zurueckgeben, das die Platzhalter referenziert.
    llm_response = "Bitte verifiziere [EMAIL_1] und ueberweise auf [IBAN_1]."
    restored = masked.unmask(llm_response)
    assert "ich@example.com" in restored
    assert "DE89370400440532013000" in restored


def test_masked_text_model_serializes() -> None:
    """MaskedText kann via Pydantic serialisiert werden (fuer Audit-Log)."""
    masker = RegexMasker()
    result = masker.mask("E-Mail: x@y.de")
    dumped = result.model_dump()
    assert "masked_text" in dumped
    assert "entities" in dumped
    assert isinstance(dumped["entities"], list)


def test_mask_does_not_alter_amounts_or_dates() -> None:
    """Betraege und Datumsangaben duerfen NICHT als PII gewertet werden."""
    masker = RegexMasker()
    text = "Rechnung 1234 vom 15.04.2026 ueber 1.234,56 EUR"
    result = masker.mask(text)
    # Betrag muss noch da sein.
    assert "1.234,56" in result.masked_text
    assert "15.04.2026" in result.masked_text
    assert "EUR" in result.masked_text
