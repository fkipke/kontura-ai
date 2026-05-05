# Kontura AI — Architektur

Dieses Dokument beschreibt die **technische Architektur** und die **Designentscheidungen** hinter Kontura AI.

> **Zielgruppe:** Entwickler, Reviewer, Future-Me. Kein Marketing.

---

## 1. Big Picture

```
┌───���─────────────────────────────────────────────────────────────────┐
│                          FRONTEND (geplant)                         │
│                  Next.js · React · TanStack Query                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS (CORS)
┌──────────────────────────────▼──────────────────────────────────────┐
│                          BACKEND API                                │
│                                                                     │
│   FastAPI (async)                                                   │
│   ├─ JWT Auth + Tenant-Isolation                                    │
│   ├─ Rate-Limiting (slowapi, per-Tenant)                            │
│   ├─ Security-Headers (OWASP)                                       │
│   ├─ Request-Context (request_id, logging)                          │
│   └─ Exception-Handlers (RFC9457 Problem Details)                   │
│                                                                     │
│   Domain-Module:                                                    │
│   ├─ /api/auth/*           — Login, Token, User                     │
│   ├─ /api/invoices/*       — Rechnungen CRUD                        │
│   └─ /api/v1/*             — Versionierte Endpoints                 │
│                                                                     │
│   AI-Layer:                                                         │
│   ├─ AIProvider (Interface)                                         │
│   ├─ AzureOpenAIProvider (Implementation)                           │
│   ├─ AuditedAIProvider (Decorator → DB-Audit-Log)                   │
│   └─ PIIMasker (vor LLM-Call)                                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ async (asyncpg + SQLAlchemy 2)
┌──────────────────────────────▼──────────────────────────────────────┐
│                       PostgreSQL 16 + pgvector                      │
│                                                                     │
│   Tabellen (mit tenant_id auf jeder!):                              │
│   ├─ tenants                                                        │
│   ├─ users                                                          │
│   ├─ invoices                                                       │
│   ├─ ai_audit_log                                                   │
│   └─ embeddings (pgvector)                                          │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTPS (EU-Region only)
┌──────────────────────────────▼──────────────────────────────────────┐
│                       Azure OpenAI (EU-West)                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Wichtige Designentscheidungen (ADRs in Kurzform)

### ADR-1: Multi-Tenancy via `tenant_id`-Column (Shared DB, Shared Schema)

**Entscheidung:** Jede Tabelle hat eine `tenant_id`-Spalte. Tenant-Trennung passiert auf Query-Ebene per WHERE-Clause, erzwungen durch das ORM.

**Alternativen erwogen:**
- Separate DB pro Tenant → zu teuer für SMB-Markt, zu komplex zu warten
- Separates Schema pro Tenant → mittlere Kosten, aber Migration-Hölle bei 100+ Tenants

**Trade-off:** Höhere Disziplin im Code (jede Query muss tenant-aware sein), dafür beste Wartbarkeit & Kosten.

### ADR-2: Stateless API mit JWT statt Session-Cookies

**Entscheidung:** JWT (HS256, 60 min Access-Token), kein Server-State.

**Begründung:**
- Horizontale Skalierung ohne Session-Sticky-Routing
- Frontend & Backend können unabhängig deployt werden
- Standard für moderne Cloud-Apps

**Risiken:** Token-Revocation muss explizit gemacht werden (Allowlist/Blocklist in Phase 2).

### ADR-3: Async-First (asyncpg + SQLAlchemy 2 async)

**Entscheidung:** Komplett async von API bis DB.

**Begründung:**
- LLM-Calls dauern lang (1-30 s) — sync würde Worker blockieren
- Mit async kann ein Worker hunderte Concurrent-Requests handhaben
- 10x bessere Resource-Nutzung als sync (gunicorn + many workers)

### ADR-4: AI-Audit-Log obligatorisch (DSGVO Art. 22)

**Entscheidung:** Jeder LLM-Call wird in `ai_audit_log` persistiert (Prompt, Response, Token-Usage, Latenz, Tenant, User).

**Begründung:**
- DSGVO Art. 22: Automatisierte Entscheidungen müssen für Betroffene nachvollziehbar sein
- Customer-Pflicht: Bei einer fehlerhaften Buchung muss man den genauen LLM-Prompt rekonstruieren können
- Implementiert via **Decorator-Pattern** (`AuditedAIProvider` umschließt `AzureOpenAIProvider`)

### ADR-5: PII-Masking VOR jedem LLM-Call

**Entscheidung:** E-Mails, IBANs, Telefonnummern werden durch Platzhalter ersetzt, bevor sie an Azure OpenAI gehen.

**Begründung:**
- Auch wenn Azure OpenAI EU-konform ist, wollen wir minimale PII-Exposition
- Defense in Depth: Selbst bei einem Azure-Breach bleiben PII-Daten lokal

### ADR-6: pgvector statt dedizierte Vector-DB (Pinecone, Weaviate)

**Entscheidung:** Embeddings werden in derselben PostgreSQL via `pgvector` gespeichert.

**Begründung:**
- Eine DB weniger zu betreiben
- Joins zwischen relationalen Daten und Embeddings möglich (z.B. „ähnliche Rechnungen *des gleichen Tenants*")
- Kostenfaktor: pgvector skaliert für unsere ~10M-Embeddings-Range völlig ausreichend

### ADR-7: ruff statt black + isort + flake8

**Entscheidung:** Ein Tool für Format + Lint statt drei.

**Begründung:**
- 10-100x schneller (Rust)
- Eine Config-Datei statt drei
- Industrie-Standard seit 2023

### ADR-8: Atomare CI-Jobs (`lint`, `typecheck`, `test` separat)

**Entscheidung:** Drei parallele Jobs statt einem Combined-Job.

**Begründung:**
- Bei rotem CI sieht man **sofort**, was kaputt ist
- Parallelisierung → schneller Feedback (3 min statt 9 min sequentiell)

---

## 3. Datenfluss: Beispiel "Rechnung wird verarbeitet"

```
1. E-Mail trifft ein (zukünftig — aktuell manueller Upload via API)
2. POST /api/invoices  (mit JWT-Auth, Rate-Limit gecheckt)
3. Backend speichert Rechnung mit status=pending, tenant_id=<aus JWT>
4. AI-Layer:
   a. Rechnungstext durch PIIMasker (E-Mails, IBANs maskiert)
   b. AzureOpenAIProvider.extract(maskierter_text)
   c. AuditedAIProvider schreibt Audit-Eintrag (Prompt, Response, Tokens)
   d. Antwort: strukturierte Rechnungsdaten (Lieferant, Betrag, Datum, ...)
5. Validierung gegen SKR03/SKR04 (Phase 3)
6. Buchungsvorschlag in DB persistiert, status=ready_for_review
7. Frontend zeigt Vorschlag → User bestätigt/korrigiert
8. Export an SAP FI oder DATEV (Phase 4)
```

---

## 4. Sicherheits-Schichten

```
Layer 1: Network        → HTTPS only, HSTS in Production
Layer 2: API            → CORS, Rate-Limiting, OWASP-Headers
Layer 3: Auth           → JWT mit Tenant-Claim
Layer 4: Authorization  → Tenant-Isolation auf jeder Query
Layer 5: AI             → PII-Masking vor LLM-Call
Layer 6: Audit          → Vollständiger Audit-Trail jedes LLM-Calls
Layer 7: Secrets        → .env (gitignored), GitHub Secret-Scanning
Layer 8: Dependencies   → Dependabot Weekly-Scan + Auto-PRs
Layer 9: CI/CD          → 3 atomare Quality-Gates auf jedem Push
```

---

## 5. Technische Schulden / TODOs

- [ ] Alembic-Migrations einführen (aktuell: `Base.metadata.create_all` für Tests)
- [ ] JWT Refresh-Token-Flow (aktuell: nur Access-Token)
- [ ] Token-Revocation (Blocklist in Redis)
- [ ] LangGraph für komplexere AI-Workflows (aktuell: Single-Shot LLM-Calls)
- [ ] Temporal für Hintergrund-Jobs (E-Mail-Polling, Batch-OCR)
- [ ] Frontend (Next.js) — Phase G
- [ ] SAP FI Integration — Phase 4
- [ ] DATEV Unternehmen Online Integration — Phase 4

---

## 6. Glossar

| Begriff | Bedeutung |
|---|---|
| **Tenant** | Ein Kundenunternehmen — eigene Daten, eigene User |
| **SKR03/SKR04** | Standardkontenrahmen der deutschen Buchhaltung |
| **DATEV** | Marktführer für Steuerberater-Software in DE |
| **SAP FI** | SAPs Finanzbuchhaltungs-Modul |
| **Audit-Log** | Persistierte Aufzeichnung aller AI-Aktionen (DSGVO Art. 22) |
| **PII** | Personally Identifiable Information (z.B. E-Mail, IBAN) |
| **JWT** | JSON Web Token — stateless Auth-Standard |
| **Rate-Limiting** | Begrenzung von Requests pro Zeitfenster |

---

*Letzte Aktualisierung: bei jedem signifikanten Architektur-Change. Diff im Git zeigt die Evolution.*