# Kontura AI

[![CI](https://github.com/fkipke/kontura-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/fkipke/kontura-ai/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-proprietary-red.svg)](#lizenz)

> KI-gestützte Rechnungsverarbeitung und Auto-Buchung für SAP FI und DATEV.

Die neue Next.js-Frontend-Basis (Sprint G3.1) liegt im Verzeichnis [`frontend/`](frontend/) und enthält Auth-Flow, geschützte Dashboard-Routen, Upload-/Status-UI für Rechnungen und die Detailansicht mit PDF-Vorschau.

**Status:** In aktiver Entwicklung — MVP geplant für Q2 2026.

---

## Was ist Kontura AI?

Kontura AI automatisiert die **Eingangsrechnungsverarbeitung** im Mittelstand:
Rechnung per E-Mail rein, KI extrahiert, validiert und kontiert nach SKR03/SKR04, Buchungsvorschlag an SAP FI oder DATEV.

**Ziel:** 80 Prozent weniger manueller Aufwand in der Kreditorenbuchhaltung bei 99 Prozent Buchungsgenauigkeit.

---

## Für wen?

Finanzleiter und Buchhaltungsteams in deutschen Mittelstandsunternehmen (50 bis 2.000 Mitarbeiter), die mit SAP FI, DATEV oder vergleichbaren Systemen arbeiten.

---

## Architektur

Kurz: **FastAPI**-Backend, **PostgreSQL + pgvector** als primärer Datenspeicher, **Azure OpenAI** als LLM-Provider mit DSGVO-konformer EU-Region-Garantie, **Multi-Tenant** über `tenant_id` auf jeder Tabelle.

→ Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Tech-Stack

| Schicht | Technologie |
|---|---|
| Backend | Python 3.11 · FastAPI · Pydantic v2 |
| AI | Azure OpenAI · LangGraph (geplant) |
| Datenbank | PostgreSQL 16 · pgvector |
| ORM | SQLAlchemy 2 (async) · asyncpg |
| Auth | JWT (HS256, 60 min Access-Token) |
| Rate-Limiting | slowapi (per Tenant) |
| Tests | pytest · pytest-asyncio · httpx |
| Quality | ruff (format + lint) · mypy (strict) |
| CI/CD | GitHub Actions · Dependabot |
| Workflows (geplant) | Temporal |
| Container | Docker · docker-compose |

---

## Sicherheit & Compliance

- **JWT-Auth** mit Tenant-Isolation auf jeder Datenbank-Query
- **Audit-Log** für jede AI-Anfrage (DSGVO Art. 22 — automatisierte Entscheidungen)
- **Rate-Limiting** pro Tenant gegen Missbrauch
- **PII-Masking** vor LLM-Calls (E-Mails, IBANs, etc.)
- **OWASP-Security-Headers** auf jeder Response
- **Secret-Scanning** + Dependency-Updates via Dependabot
- **EU-Region-Pinning** für Azure OpenAI (keine US-Datenflüsse)

---

## Lokales Setup

### Voraussetzungen

- **Python 3.11+**
- **uv** (Package-Manager) — [Installations-Guide](https://docs.astral.sh/uv/)
- **Docker Desktop** (für Postgres + pgvector lokal)
- **Git**

### Installation

```bash
# 1. Repo klonen
git clone git@github.com:fkipke/kontura-ai.git
cd kontura-ai

# 2. Dependencies installieren
uv sync

# 3. .env aus Template kopieren und Secrets eintragen
cp .env.example .env
# Editor öffnen, OPENAI_API_KEY etc. eintragen

# 4. Postgres + pgvector starten
docker compose up -d

# 5. Datenbank-Migrations laufen lassen (falls nötig)
# (TODO: Alembic-Schritt sobald Migrations eingeführt)

# 6. Server starten
uv run uvicorn kontura.main:app --reload
```

API verfügbar unter: **http://localhost:8000**
OpenAPI-Doku: **http://localhost:8000/docs**

---

## Entwicklung

### Code-Quality lokal prüfen

```bash
# Format-Check (CI prüft das gleiche)
uv run ruff format --check .

# Auto-Format (vor Commit)
uv run ruff format .

# Lint
uv run ruff check .

# Auto-Fix Lint-Issues
uv run ruff check --fix .

# Type-Check
uv run mypy src/ tests/

# Tests
uv run pytest
```

### CI-Pipeline

Bei jedem Push auf `main` und jedem Pull-Request laufen automatisch:
- **lint** (ruff format + check)
- **typecheck** (mypy strict)
- **test** (pytest gegen echtes Postgres + pgvector)

→ Details: [`.github/workflows/README.md`](.github/workflows/README.md)

---

## G2.1 — AI Extraction

### Endpoints

| Methode | Pfad | Beschreibung |
|---|---|---|
| `POST` | `/api/v1/invoice-files` | Upload + auto-trigger KI-Extraktion |
| `POST` | `/api/v1/invoice-files/{id}/extract` | Manuelle Re-Extraktion (`?force=true` erzwingt) |
| `GET` | `/api/v1/invoice-files/{id}/extraction` | Status + Ergebnis der letzten Extraktion |

### Status-Machine

```
Upload
  │
  ▼
pending ──► processing ──► completed
              │
              ▼
            failed
              │
              └──► processing (Re-Trigger)
```

- **pending**: Datei hochgeladen, Extraktion noch nicht gestartet
- **processing**: LLM-Call läuft (atomar gesetzt, für spätere Worker-Erweiterung)
- **completed**: Extraktion erfolgreich, `Invoice` angelegt und gelinkt
- **failed**: LLM-Fehler oder Schema-Validierungsfehler, `extraction_error` enthält Grund

### Architektur-Entscheidungen

- **GPT-4o Vision**: kein separater OCR-Schritt — Modell liest direkt PDF-Seiten als PNG
- **PyMuPDF**: PDF-Rendering pure-Python, kein Poppler/Ghostscript nötig
- **FastAPI BackgroundTasks**: kein Redis, kein Celery — reicht für MVP
- **Structured Outputs** (`response_format=json_schema, strict=True`): garantiert valides JSON
- **Auto-Link**: `(tenant_id, invoice_number)` UniqueConstraint verhindert Duplikate

### Dependency-Updates

Dependabot prüft wöchentlich (montags) auf Updates für:
- Python-Pakete (pip + uv.lock)
- GitHub Actions

Konfiguration: [`.github/dependabot.yml`](.github/dependabot.yml)

---

## G4.0 — DATEV-Export

- **Endpoint:** `GET /api/v1/exports/datev?from=YYYY-MM-DD&to=YYYY-MM-DD`
- **Format:** DATEV-EXTF Buchungsstapel CSV (`windows-1252`, `;`, CRLF)
- **Konfiguration:** `DATEV_CONSULTANT_NUMBER`, `DATEV_CLIENT_NUMBER`, `DATEV_FISCAL_YEAR_START`, `DATEV_ACCOUNT_LENGTH`, `DATEV_DEFAULT_EXPENSE_ACCOUNT`, `DATEV_DEFAULT_CREDITOR_ACCOUNT`
- **Hinweis:** `BU-Schlüssel` bleibt im Export leer und wird nach dem Import in DATEV manuell gesetzt.
- **Ausblick:** ZUGFeRD/XML folgt in G4.1, Lieferanten-Auto-Mapping folgt in G4.3.

---

## Roadmap

- [x] **F1 — JWT-Auth + Multi-Tenancy:** Tenant-isolierte Auth via JWT
- [x] **F2 — AI-Audit-Log:** Vollständige DSGVO-konforme Aufzeichnung jeder LLM-Interaktion
- [x] **F3 — Rate-Limiting:** Per-Tenant Limits gegen Missbrauch
- [x] **F4 — CORS + Security-Headers:** OWASP-Basics + Frontend-ready
- [x] **H1 — CI-Pipeline:** Automatische Quality-Gates auf jedem Push
- [x] **H2 — Dependabot + Security-Scanning:** Automatische Update-PRs
- [x] **G2.0 — Invoice File Upload:** `POST /api/v1/invoice-files` (PDF/PNG/JPEG), `GET /api/v1/invoice-files`, `GET /api/v1/invoice-files/{id}` — mit Magic-Byte-Validierung, SHA-256-Deduplication und Tenant-Isolation
- [x] **G2.1 — KI-Extraktion:** GPT-4o Vision, structured outputs, async via FastAPI BackgroundTasks, auto-link zu Invoice
- [x] **G4.0 — DATEV-EXTF-Buchungsstapel-Export:** CSV-Export geprüfter Rechnungen (`is_reviewed=true`) im Format Windows-1252
- [ ] **G1 — Frontend (Next.js):** Login, Rechnungsliste, Detail-Ansicht
- [ ] **Phase 3 — Validation & Booking:** SKR03-Kontierung, Buchungsvorschlag
- [ ] **Phase 4 — Integrationen:** SAP FI, DATEV Unternehmen online
- [ ] **Phase 5 — Pilotkunden:** Onboarding, Produktions-Deployment

---

## Beitragen

Aktuell ist das Projekt in einer **frühen Entwicklungsphase** und wird primär vom Repo-Owner gepflegt.
Bei Interesse an einer Mitarbeit oder einem Pilotkunden-Setup: **bitte direkt Kontakt aufnehmen**.

---

## Kontakt

**Fabian Kipke** · [GitHub @fkipke](https://github.com/fkipke)

---

## Lizenz

Proprietär. Alle Rechte vorbehalten. © 2026 Fabian Kipke.

---

*Dieses Repository dokumentiert die laufende Entwicklung. Inhalte, Architektur und Features können sich kurzfristig ändern.*