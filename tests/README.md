# Test Suite Layout

Three layers, three deps profiles. DevOps wires these into the CI matrix.

```
tests/
  conftest.py            isolated SQLite test DB + seeded testadmin/3 debts
  test_*.py              unit + integration (existing 78 tests)
  smoke/                 fast ASGI smoke tests — Phase 1
  e2e/                   Playwright browser tests — Phase 2 (dockerised)
```

## Layer summary

| Layer | Marker | Transport | Container? | Tests | Local runtime | CI budget |
| --- | --- | --- | --- | --- | --- | --- |
| Unit + Integration | none | `httpx.AsyncClient` (ASGI) | no | 78 | ~17 s | <60 s |
| Smoke | `smoke` | `httpx.AsyncClient` (ASGI) | no | 27 | ~9 s | <60 s |
| E2E | `e2e` | Playwright Chromium | yes (Docker compose) | 4 flows / 8 assertions | ~90 s incl. boot | <5 min |

Combined unit + integration + smoke runs in **~23 s on a 2024 MacBook Pro**.

## Commands

```bash
# Unit + integration (everything that is NOT smoke or E2E)
python3 -m pytest tests/ -m "not smoke and not e2e" -v

# Smoke (ASGI, no docker)
python3 -m pytest tests/smoke/ -m smoke -v

# E2E — DevOps owns the up/down lifecycle in the pipeline
docker compose -f tests/e2e/docker-compose.test.yml up -d --build
python3 -m pytest tests/e2e/ -m e2e -v
docker compose -f tests/e2e/docker-compose.test.yml down -v

# Everything except E2E (covers the default CI fast path)
python3 -m pytest tests/ -m "not e2e" -v

# Absolutely everything (assumes E2E stack is up)
python3 -m pytest tests/ -v
```

## Required env vars per layer

| Var | Layer | Default | Notes |
| --- | --- | --- | --- |
| `SECRET_KEY` | all | (set by `tests/conftest.py`) | Must be present when `APP_ENV=production` |
| `DATABASE_URL` | all | (set by `tests/conftest.py`) | Forced to isolated SQLite for unit/integration/smoke |
| `SMOKE_ADMIN_USER` | smoke | `smokeadmin` | Optional override |
| `SMOKE_ADMIN_PASS` | smoke | `SmokePassword123!` | Optional override |
| `E2E_BASE_URL` | e2e | `http://localhost:5050` | Where Playwright sends the browser |
| `CI_ADMIN_USER` | e2e | `ci_admin` | Read by `scripts/init_db.py` inside the app container AND by the e2e fixtures |
| `CI_ADMIN_PASS` | e2e | `CiAdminPass1234!` | Same as above; ≥12 chars |
| `ALLOW_REGISTRATION` | e2e (compose sets `true`) | `false` | Optional in dev |

## Dependencies

- `requirements.txt` — runtime + unit/integration/smoke (`pytest`, `httpx`,
  `anyio`).
- `requirements-dev.txt` — adds `pytest-playwright` for E2E only. Install
  Chromium once: `python3 -m playwright install --with-deps chromium`.

## Why split the layers

- **Unit + integration** stays the existing fast loop devs already run.
- **Smoke** is a contract layer: every public + authed surface, security
  middleware, CSRF, and the `/docs` prod kill-switch. ~27 tests, all on
  ASGI transport so they run anywhere `pytest` runs (no docker, no
  network). Keeps CI gate lightweight.
- **E2E** is the real-browser sanity net. Runs against the production
  Docker image + Postgres container. Slower; treat as a pre-deploy gate
  rather than per-PR.
