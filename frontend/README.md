# Kontura — Frontend

Next.js 15 App Router · React 19 · TanStack Query · shadcn/ui · Tailwind

Das Frontend von [Kontura AI](../README.md). Premium-UI mit serverseitiger Proxy-Schicht zum FastAPI-Backend und httpOnly-Cookie-Auth (kein Token im JS-Land).

## Quick Start

```bash
npm install
cp .env.example .env.local
npm run dev
```

App: <http://localhost:3000> (Backend muss unter <http://localhost:8000> laufen.)

## Quality-Gates

```bash
npm run lint        # ESLint
npm run typecheck   # tsc --noEmit
npm run build       # Production-Build
npm test            # Vitest Unit-Tests
```

## Umgebungsvariablen

| Variable | Default | Zweck |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | URL des FastAPI-Backends für serverseitige Proxy-Calls |

## Verzeichnis-Überblick

```
app/
  (auth)/        Login & Register (öffentlich)
  (app)/         Geschützte Routen (Dashboard, Rechnungen, Export)
  api/auth/      Route-Handler: Login → setzt httpOnly-Cookie
  api/proxy/     Proxy: hängt Bearer-Token serverseitig an Backend-Requests
components/
  auth/          Login/Register-Formulare
  exports/       DATEV-Export mit Live-Vorschau
  invoices/      Liste, Detail-View, Editor, Validierungs-Panel
  layout/        Top-Nav, Theme-Toggle
  ui/            shadcn/ui Primitives (Button, Card, Table …)
lib/
  api/           Typisierte API-Clients + Zod-Schemas
  auth/          httpOnly-Cookie-Helfer
tests/unit/      Vitest Unit-Tests
```

## Auth-Flow (kurz)

1. `POST /api/auth/login` (Next.js Route-Handler) ruft FastAPI-Backend auf.
2. Erfolgreicher JWT landet in httpOnly-Cookie — nie im JS lesbar.
3. Alle Client-Calls gehen an `/api/proxy/*`; der Proxy hängt den Bearer-Token serverseitig an.
4. Middleware schützt `(app)/*`-Routen und leitet bei fehlender Session auf `/login` um.

## Theming

Light + Dark Mode via `next-themes`, Theme-Toggle in der Top-Nav. Farbsystem aus shadcn/ui Tokens, einheitlich über CSS-Variablen.
