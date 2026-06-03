"""Deterministische Vendor-Name-Normalisierung fuer Fuzzy-Matching."""

from __future__ import annotations

import re
import unicodedata

_LEGAL_FORM_PATTERNS = [
    r"\bgesellschaft mit beschränkter haftung\b",
    r"\bgmbh\s*&\s*co\.?\s*kg\b",
    r"\bgmbh\s*&\s*co\.?\s*kgaa\b",
    r"\baktiengesellschaft\b",
    r"\bgmbh\b",
    r"\bag\b",
    r"\bkg\b",
    r"\bkgaa\b",
    r"\bohg\b",
    r"\bug\s*\(haftungsbeschränkt\)\b",
    r"\bug\b",
    r"\bse\b",
    r"\bgbr\b",
    r"\bev\b",
    r"\be\.?v\.?\b",
    r"\bsarl\b",
    r"\bs\.?a\.?\b",
    r"\bb\.?v\.?\b",
    r"\bnv\b",
    r"\bltd\.?\b",
    r"\bllc\b",
    r"\binc\.?\b",
    r"\bcorp\.?\b",
]


def normalize_vendor_name(raw: str) -> str:
    """Normalisiert einen Vendor-Namen fuer deterministisches Matching."""
    if not raw:
        return ""

    nfkd = unicodedata.normalize("NFKD", raw)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_accents.lower()

    for pattern in _LEGAL_FORM_PATTERNS:
        lowered = re.sub(pattern, " ", lowered, flags=re.IGNORECASE)

    no_special = re.sub(r"[^a-z0-9\s\-]", " ", lowered)
    collapsed = re.sub(r"\s+", " ", no_special).strip()
    result = collapsed[:200]

    if not result:
        return raw.lower().strip()[:200]

    return result
