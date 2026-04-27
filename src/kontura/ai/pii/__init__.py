"""PII-Masking-Layer fuer Kontura AI.

Schuetzt Customer-Daten, BEVOR sie an externe LLMs (OpenAI etc.) gehen.
Einsatz: jede Stelle, wo Rechnungstext zu einem Provider geht.

Senior-Pattern: PIIMasker ist ein Protocol, dahinter steht aktuell unser
RegexMasker. Spaeter swap-bar gegen Presidio o.ae., ohne Aufrufer-Aenderung.
"""

from kontura.ai.pii.base import MaskedText, PIIEntity, PIIMasker
from kontura.ai.pii.regex_masker import RegexMasker

__all__ = ["MaskedText", "PIIEntity", "PIIMasker", "RegexMasker"]
