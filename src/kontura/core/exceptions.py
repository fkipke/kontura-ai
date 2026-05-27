"""Domain-Exception-Hierarchie fuer Kontura AI.

Senior-Pattern: Domain-Exceptions, keine HTTP-Exceptions im Service-Layer
========================================================================
Services und Repositories sollen NICHTS von HTTP wissen. Sie werfen
Domain-Begriffe ('TenantAlreadyExists', 'InvoiceNotFound'). Erst der
HTTP-Layer (api/error_handlers.py) mappt diese auf Statuscodes.

Vorteile:
- Service ist isoliert testbar - kein FastAPI-TestClient noetig.
- Wenn wir spaeter einen CLI- oder gRPC-Layer dranhaengen, fangen die
  Domain-Exceptions ab und mappen sie auf ihre eigene Fehlerwelt.
- 'NotFoundError' kann je nach Endpoint 404 ODER 403 sein - die Entscheidung
  passiert pro Endpoint, nicht im Service.

Hierarchie
==========
KonturaError                 (alle Domain-Errors)
├── ConflictError            -> 409
├── NotFoundError            -> 404
├── ForbiddenError           -> 403
├── UnauthorizedError        -> 401
└── ValidationError          -> 422
"""

from __future__ import annotations


class KonturaError(Exception):
    """Wurzel aller Domain-Exceptions in Kontura AI."""


class ConflictError(KonturaError):
    """Eine Ressource existiert schon, Konflikt mit Unique-Constraint o.ae.

    Mapping: HTTP 409 Conflict.
    """


class NotFoundError(KonturaError):
    """Eine angeforderte Ressource wurde nicht gefunden.

    Mapping: HTTP 404 Not Found.
    """


class ForbiddenError(KonturaError):
    """User ist authentifiziert, aber darf die Aktion nicht ausfuehren.

    Mapping: HTTP 403 Forbidden.
    """


class EmailNotVerifiedError(ForbiddenError):
    """Login blockiert, bis die E-Mail-Adresse bestaetigt wurde."""

    code = "email_not_verified"


class UnauthorizedError(KonturaError):
    """User ist NICHT authentifiziert (Token fehlt/ungueltig).

    Mapping: HTTP 401 Unauthorized.
    """


class DomainValidationError(KonturaError):
    """Geschaeftsregel verletzt (z.B. Rechnungsdatum in der Zukunft).

    Hinweis: NICHT verwechseln mit Pydantic-Validation - die wird automatisch
    von FastAPI als 422 zurueckgegeben. Diese Klasse hier ist fuer Regeln,
    die ERST nach erfolgreicher Schema-Validation gepruefte werden.

    Mapping: HTTP 422 Unprocessable Entity.
    """
