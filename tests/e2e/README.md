# E2E Tests

Browser-driven Playwright tests against a dockerised debt-tracker stack.

## Layout

```
tests/e2e/
  conftest.py                 fixtures + readiness gate
  docker-compose.test.yml     Postgres 16 + app (production Dockerfile)
  test_login_flow.py          login, invalid creds, logout
  test_strategy_change.py     /plan toggle persists to /settings
  test_remit_flow.py          remit calculation + allocation render
  test_debt_crud.py           create / edit / delete with type-name confirm
```

## Required env vars

| Var | Default | Purpose |
| --- | --- | --- |
| `E2E_BASE_URL` | `http://localhost:5050` | Where pytest fixtures send the browser |
| `CI_ADMIN_USER` | `ci_admin` | Username seeded by `scripts/init_db.py` inside the app container |
| `CI_ADMIN_PASS` | `CiAdminPass1234!` | Password seeded by `scripts/init_db.py` inside the app container |

`CI_ADMIN_*` is read both by the compose file (passed into the app
container) and by the test fixtures (used during `page.fill('username')`).
Set the same value in both places.

## Run locally

```bash
# 1. Install dev deps + Chromium
pip install -r requirements-dev.txt
python3 -m playwright install --with-deps chromium

# 2. Bring the stack up (builds the production image, seeds admin)
docker compose -f tests/e2e/docker-compose.test.yml up -d --build

# 3. Run the suite
python3 -m pytest tests/e2e/ -m e2e -v

# 4. Tear down
docker compose -f tests/e2e/docker-compose.test.yml down -v
```

## Notes for the DevOps Engineer

- Chromium-only on purpose. Adding Firefox/WebKit doubles install time
  and gives no extra signal on this app.
- `_wait_for_app` autouse fixture polls `/api/healthz` for up to 60 s
  before any test runs, so a slow Postgres boot won't flake the suite.
- The compose `app` service overrides the entrypoint to run
  `scripts/init_db.py` first (idempotent admin seed), then the normal
  `start.sh`. Re-running `up -d` is safe.
- Healthchecks: Postgres 3 s interval / 20 retries; app 5 s interval /
  20 retries with a 10 s start-period grace. Gives ~110 s total before
  compose marks the stack unhealthy.
- The Postgres container does NOT publish a host port — the app talks
  to it on the compose network. This avoids collisions if the dev
  `docker-compose.yml` is also up locally.
