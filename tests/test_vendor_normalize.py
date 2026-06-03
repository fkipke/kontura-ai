from __future__ import annotations

from kontura.api.vendor_mappings.normalize import normalize_vendor_name


def test_strips_gmbh() -> None:
    assert normalize_vendor_name("ACME Deutschland GmbH") == "acme deutschland"


def test_strips_gmbh_co_kg() -> None:
    assert normalize_vendor_name("Müller GmbH & Co. KG") == "muller"


def test_strips_ag_kg_ug_ev() -> None:
    assert normalize_vendor_name("K+S AG KG UG e.V.") == "k s"


def test_folds_umlauts() -> None:
    assert normalize_vendor_name("Müller") == "muller"


def test_folds_accents() -> None:
    assert normalize_vendor_name("Café") == "cafe"


def test_lowercases() -> None:
    assert normalize_vendor_name("ACME") == "acme"


def test_collapses_whitespace() -> None:
    assert normalize_vendor_name("  ACME    Lieferant   GmbH  ") == "acme lieferant"


def test_handles_empty_string() -> None:
    assert normalize_vendor_name("") == ""


def test_handles_only_legal_form() -> None:
    assert normalize_vendor_name("GmbH") == "gmbh"


def test_truncates_at_200_chars() -> None:
    raw = f"{'a' * 210} GmbH"
    assert len(normalize_vendor_name(raw)) == 200


def test_preserves_unique_distinguishers() -> None:
    assert normalize_vendor_name("ACME Nord GmbH") != normalize_vendor_name("ACME Süd GmbH")
