# Kontura AI

[![CI](https://github.com/fkipke/kontura-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/fkipke/kontura-ai/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 15](https://img.shields.io/badge/next.js-15-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**KI-gestützte Eingangsrechnungsverarbeitung mit DATEV-Export.**

PDF rein → GPT-4o liest aus → Plausibilitätsprüfung → Vier-Augen-Prüfung → DATEV-EXTF-Buchungsstapel raus.

---

## ▶ Demo (2:47)

🎬 **[Video-Demo auf YouTube ansehen](https://youtu.be/gf5iux2KypM)**

End-to-End-Walkthrough: Login → Dashboard → PDF-Upload mit Live-Extraktion → Validierungswarnung → Geprüft-Markierung mit Audit-Trail → DATEV-Export-Vorschau → CSV-Download → Dark Mode.

---

## Was es löst

Buchhaltungsteams in deutschen Mittelständlern tippen in der Regel **Eingangsrechnungen aus PDFs ab**, kontieren von Hand und exportieren nach DATEV. 80 % der Zeit ist Maschinenarbeit, die jeder Buchhalter hasst.

Kontura erledigt diese 80 % automatisch, die fachliche Prüfung bleibt hierbei jedoch beim Menschen. Vier-Augen-Prinzip, GoBD-konformer Audit-Trail, keine Black-Box-Entscheidungen.

---

## Tech-Stack

| Schicht | Technologie |
|---|---|
| **Backend** | Python 3.11 · FastAPI · Pydantic v2 |
| **Frontend** | Next.js 15 (App Router) · React 19 · TanStack Query · shadcn/ui · Tailwind |
| **KI** | OpenAI GPT-4o Vision (structured outputs) · ZUGFeRD-/XRechnung-Parser |
| **Datenbank** | PostgreSQL 16 · pgvector · SQLAlchemy 2 async · Alembic |
| **Auth** | JWT (HS256) · httpOnly-Cookies · Per-Tenant-Isolation |
| **Quality** | pytest · vitest · ruff · mypy strict · GitHub Actions CI |
| **Container** | Docker · docker-compose |

---

## Was funktioniert

Statt einer Wunsch-Roadmap: **was tatsächlich gebaut und getestet ist** in diesem Stand.

### Multi-Tenant-Auth mit Tenant-Isolation
JWT mit per-Tenant-Filter auf jeder DB-Query — architektonisch erzwungen via Repository-Pattern, nicht nur applikationslogisch geprüft. E-Mail-Verifizierung mit Token-Cooldown, Rate-Limiting pro Tenant (60/min), Brute-Force-Schutz pro IP (10/min auf Login).

### Hybride Rechnungs-Extraktion
Pipeline mit drei Pfaden, in dieser Reihenfolge probiert:

1. **XRechnung (UBL & CII)** — deterministisches XML-Parsing, kein LLM-Call nötig
2. **ZUGFeRD v2** — eingebettete XML-Auswertung mit Profil-Warnung bei MINIMUM (zu wenig Daten für Buchung)
3. **GPT-4o Vision** als Fallback — PyMuPDF rendert PDF zu PNG, OpenAI structured outputs garantiert valides JSON

Status-Machine `pending → processing → completed | failed` ist atomar gesetzt — ein späterer Wechsel von BackgroundTasks auf Celery oder Temporal bleibt transparent.

### Editor mit Optimistic Locking
Buchhalter*innen können KI-Ergebnisse korrigieren. Version-Inkrement bei jedem Update, **409-Konflikt** bei paralleler Bearbeitung mit aktuellem Server-Stand im Response-Body. Vollständiger Audit-Trail in `invoice_edits` (GoBD-konform: alter Wert + neuer Wert + User-ID + Timestamp pro geändertem Feld).

### DATEV-Export mit Live-Vorschau
EXTF-Buchungsstapel-CSV (Windows-1252, ;-getrennt, CRLF — DATEV-Spezifikation 2020). Das UI zeigt **vor** dem Download Anzahl, Brutto/Netto/USt-Summen, Wirtschaftsjahr-Filter und jede einzelne Rechnung mit ihrer Konten-Zuordnung. Quick-Range-Buttons (Diesen Monat / Dieses Jahr / Alle Zeit) statt umständlicher Datepicker.

### Plausibilitätsprüfung in Echtzeit
Soft-Warnings bei `Netto + USt ≠ Brutto`, Rechnungsdatum in Zukunft, unüblicher Währung — **nicht-blockierend**, weil Buchhalter*innen mit Fachwissen entscheiden, nicht der Validator.

### DSGVO-Audit-Log für jeden LLM-Call
Input-Hash (PII-gemaskt), Output, Token-Verbrauch, Modell, Tenant, Timestamp — vollständig persistiert wegen Art. 22 DSGVO (automatisierte Einzelentscheidung im rechtlichen Sinn).

### Security
- OWASP Security-Headers auf jeder Response (CSP, X-Frame-Options, Referrer-Policy)
- HSTS optional aktivierbar (in Production AN)
- CORS-Whitelist statt Wildcard
- Dependabot wöchentlich für Python + GitHub Actions
- Secret-Scanning aktiv

---

## Architektur in einem Satz

**FastAPI-Backend** (Repository-Pattern, async durchgängig) gegen **PostgreSQL** mit pgvector-Erweiterung, **Next.js-Frontend** mit serverseitiger Proxy-Schicht und httpOnly-Cookie-Auth, **OpenAI** für die Felderkennung mit deterministischen XML-Pfaden vorgeschaltet — alles tenant-isoliert ab der Datenbankzeile.

Detaillierte Architektur-Doku: [`docs/`](docs/)

---

## Lokales Setup

### Voraussetzungen
- **Python 3.11+**
- **Node.js 20+** und **npm**
- **uv** ([Installation](https://docs.astral.sh/uv/))
- **Docker Desktop** (für Postgres + pgvector)

### Backend

```bash
git clone https://github.com/fkipke/kontura-ai.git
cd kontura-ai

cp .env.example .env          # OPENAI_API_KEY eintragen
uv sync                       # Python-Dependencies installieren
docker compose up -d          # Postgres + pgvector starten
uv run alembic upgrade head   # DB-Migrations laufen lassen
uv run uvicorn kontura.main:app --reload --port 8000
```

Backend: <http://localhost:8000> · API-Doku: <http://localhost:8000/docs>

### Frontend

```bash
cd frontend
cp .env.example .env.local    # Default zeigt auf localhost:8000
npm install
npm run dev
```

Frontend: <http://localhost:3000>

### Demo-Daten seeden (optional)

```bash
uv run python scripts/seed_demo_tenant.py
```

Legt einen `demo@kontura.ai`-User mit 50 deutschen Demo-Rechnungen an (12 typische Lieferanten, realistische Beträge, ~30 % bereits geprüft).

---

## Entwicklung

```bash
uv run ruff check --fix .       # Lint + Auto-Fix
uv run ruff format .            # Format
uv run mypy src/ tests/         # Type-Check (strict)
uv run pytest                   # Backend-Tests
cd frontend && npm test         # Frontend-Tests (vitest)
```

CI: `lint`, `typecheck`, `test` als required checks auf jedem PR (siehe [`.github/workflows/`](.github/workflows/)).

---

## Lizenz

[MIT](LICENSE) — © 2026 Fabian Kipke

---

## Kontakt

**Fabian Kipke** · [github.com/fkipke](https://github.com/fkipke)
