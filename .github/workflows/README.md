# CI Workflows

## `ci.yml`

Läuft bei jedem Push auf `main` und bei jedem PR.

**3 parallele Jobs:**

| Job | Tool | Was |
|---|---|---|
| `lint` | ruff | Format-Check + Lint |
| `typecheck` | mypy | Statische Typprüfung |
| `test` | pytest | Tests gegen echtes Postgres+pgvector |

**Setup-Geschwindigkeit:** ~3 Min (kalt), ~1 Min (mit Cache).

## Branch-Protection (manuell einzurichten)

Nach dem ersten erfolgreichen Run im Repo unter:
**Settings → Branches → Branch protection rules → Add rule** für `main`:

- ✅ Require status checks to pass before merging
  - `lint`, `typecheck`, `test` als Required
- ✅ Require branches to be up to date before merging
- ✅ Do not allow bypassing the above settings (auch nicht für Admins)

So kann **kein** Commit mehr nach `main`, der die CI nicht besteht.