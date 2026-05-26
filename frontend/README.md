# Kontura Frontend (G3.1 Foundation)

Premium-UI für Kontura mit Next.js (App Router), TanStack Query und einer serverseitigen Proxy-Schicht zum FastAPI-Backend.

## Quick Start

```bash
pnpm install
cp .env.example .env.local
pnpm dev
```

Qualitätssicherung:

```bash
pnpm lint
pnpm typecheck
pnpm build
pnpm test
```

## Umgebungsvariablen

- `NEXT_PUBLIC_API_BASE_URL` (Standard: `http://localhost:8000`)

Das Backend muss lokal unter `http://localhost:8000` laufen.

## Ordnerüberblick

- `app/` – Routen, Layouts, Route Handler (`/api/auth/*`, `/api/proxy/*`)
- `components/` – UI (Auth, Layout, Invoices, primitives)
- `lib/api/` – typisierte API-Clients + Zod-Schemas
- `lib/auth/` – httpOnly-Cookie-Helfer
- `tests/unit/` – Vitest Unit-Tests

## Auth-Flow (kurz)

1. Login/Register sendet Credentials an Next-Route-Handler (`/api/auth/login`, `/api/auth/register`).
2. Der Handler ruft FastAPI auf und setzt den JWT in einen `httpOnly` Cookie.
3. Client-Komponenten sprechen nur mit `/api/proxy/*`; der Proxy hängt den Bearer Token serverseitig an.
4. Middleware schützt App-Routen und leitet bei fehlender Session auf `/login` um.
