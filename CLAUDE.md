# Debt Tracker — Claude Project Instructions

## What This Is
FastAPI + SQLAlchemy (async) + Jinja2 web app for personal debt repayment tracking.
Filipino OFW context: income SAR, debts PHP, avalanche/snowball payoff planning.

## Stack
- **Backend**: FastAPI, SQLAlchemy (async), Alembic, Pydantic
- **DB**: SQLite (dev), Postgres (prod via Docker)
- **Frontend**: Jinja2 templates, vanilla JS, Chart.js, Tailwind (CDN)
- **AI**: OpenAI `gpt-4o-mini` for debt analysis (optional, keyed via settings)
- **Auth**: Session-based (starlette `SessionMiddleware`), bcrypt password hash

## Project Layout
```
app/
  __init__.py        # create_app(), router registration
  config.py          # settings, env loading, load_env_file(), hash_password(), verify_password(), save_env_value()
  dependencies.py    # get_current_user(), NotAuthenticated, require_admin
  templating.py      # Jinja2 env setup
  storage.py         # legacy shim (unused, keep for reference)
  db/
    base.py          # async engine, session factory, get_db
    models.py        # User, Debt, MonthlyEntry, AiCache
    crud.py          # all DB ops — see Key CRUD Functions below
    adapter.py       # build_data_dict(), debt_name_to_id()
  routes/
    auth.py          # GET/POST /login, GET /logout
    pages.py         # /, /add, /edit/{month}, /plan, /remit, /settings
    api.py           # GET /api/analysis
    debts.py         # GET/POST /debts, /debts/{id}/edit, /debts/{id}/delete, /debts/reorder
    admin.py         # GET /admin, POST /admin/users/create|{id}/reset-password|{id}/delete
  services/
    ai.py            # get_analysis(), compute_hash() — OpenAI call + AiCache
    planner.py       # compute_plan(), allocate_budget(), latest_month()
templates/           # Jinja2 HTML (extend base.html, set active=)
static/              # chart.min.js, any CSS overrides
alembic/             # DB migrations
scripts/             # one-off admin/migration scripts
```

## DB Models (SQLAlchemy mapped_column style)
- `User` — id, username, password_hash, is_admin, income_config (JSONB), created_at
- `Debt` — id, user_id, name, type, apr_monthly_pct, note, is_fixed, fixed_monthly, fixed_ends (YYYY-MM), fixed_reduced_monthly, fixed_reduced_threshold, sort_order
- `MonthlyEntry` — id, user_id, debt_id, month (YYYY-MM), balance, min_due, payment, paid_on, due_date, note
- `AiCache` — user_id (PK), data_hash, html, generated_at

## Key CRUD Functions (app/db/crud.py)
- Users: `get_user_by_username`, `get_user_by_id`, `get_all_users`, `create_user`, `update_user_password`, `update_income_config`, `delete_user`
- Debts: `get_debts(db, user_id)`, `get_debt_by_id(db, debt_id, user_id)`, `create_debt(db, user_id, **kwargs)`, `update_debt(db, debt, **kwargs)`, `delete_debt(db, debt_id, user_id)`, `reorder_debts(db, user_id, ordered_ids)`
- Entries: `get_months`, `get_entries_for_month`, `get_all_entries`, `upsert_entry`, `delete_entries_for_month`
- AI: `get_ai_cache(db, user_id)`, `set_ai_cache(db, user_id, data_hash, html)`

## income_config JSON shape (stored on User.income_config)
```json
{
  "monthly_sar": 8000,
  "expenses_sar": 2000,
  "sar_to_php": 15.2,
  "phone": { "monthly_sar": 200, "ends": "2026-07" },
  "ofw_mode": true,
  "currency_symbol": "₱",
  "income_currency": "SAR"
}
```

## data dict shape (built by adapter.build_data_dict)
```python
{
  "months": { "2025-01": { "DebtName": { "balance": 0, "min_due": 0, ... } } },
  "debts":  { "DebtName": { "type": "credit_card", "apr_monthly_pct": 3.5 } },
  "income_config": { ... },
  "fixed_payments": { "DebtName": { "monthly": 5000, "ends": "2027-06" } },
}
```

## Key Conventions
- Route handlers: auth check → load data → render/redirect
- `_load_user_data(db, user)` — single source of truth for page data
- `data["months"]` keyed by `"YYYY-MM"` strings
- `data["debts"]` keyed by debt name strings
- Debt types: `"credit_card"` | `"personal_loan"` | `"other"`
- All monetary values PHP unless noted
- Never commit `debts.json`, `.env`, CSV/PDF — personal financial data

## Coding Rules
- PEP8, 4-space indent, snake_case, UPPER_SNAKE constants
- Early returns, explicit error handling, no deep nesting
- No hand-holding comments
- No `Co-Authored-By` trailers in commits

## MONTHLY_INPUT_GUIDE.md
Update after changes to add/edit month flow, debt fields, or income config. Documents monthly data entry — keep accurate.

## Templates — Patterns
- All extend `base.html`, set `active=` context var for nav highlight
- Nav active values: `dashboard`, `add`, `debts`, `remit`, `plan`, `settings`
- CSS classes: `.section`, `.card`, `.grid`, `.btn`, `.btn-primary`, `.btn-success`, `.btn-back`, `.badge`, `.badge-green/.red/.yellow`, `.qbtn`, `.alert`, `.alert-success/.alert-error`
- Tables: add `table-card` for mobile card-style collapse; `td` needs `data-label=` for mobile labels
- Delete confirmation: type-the-name input enables submit (see `edit_debt.html`)

## Testing
```
python -m pytest tests/ -v
```
- Stack: `pytest` + `httpx.AsyncClient` + `anyio`
- `tests/conftest.py` — isolated SQLite test DB (`tests/test_debttracker.db`), auto-created and torn down
- DB overridden via `os.environ["DATABASE_URL"]` before app import — must stay at top of conftest
- Seed: 1 admin user + 3 debts per session
- 25 tests: auth, pages, debts CRUD+reorder, admin user management
- Test DB excluded from Claude context via `.claudeignore`

## Do Not Touch
- `alembic/versions/` — never edit manually, generate with `alembic revision`
- Session secret in `.env` (`SECRET_KEY`) — never log or expose

## Settings Actions (POST /settings, action= field)
- `mode` — toggle `ofw_mode` bool in income_config + session
- `rate` — update `sar_to_php` in income_config
- `income` — update `monthly_sar`, `expenses_sar`, `phone.monthly_sar`, `phone.ends`
- `apikey` — save OPENAI_API_KEY to .env via `save_env_value()`
- `password` — verify current, enforce 12-char min, update hash

## DB Dialect Notes
- `income_config` uses `sa.JSON` (not `JSONB`) — works SQLite + Postgres
- `created_at` uses Python-side `default=datetime.utcnow` (not `server_default=func.now()`) — `now()` Postgres-only
- Alembic migration uses `CURRENT_TIMESTAMP` (ANSI SQL, both dialects)
- Dev default DB: `sqlite+aiosqlite:///debttracker.db` — set `DATABASE_URL` env var for Postgres

## Init / First Run
```
python scripts/init_db.py
```
- Generates `SECRET_KEY` in `.env` if missing
- Runs `alembic upgrade head`
- Prompts for admin username + password if no users exist
- Idempotent — safe to re-run

## Dockerfile Security
- Base: `python:3.13-slim`
- Non-root user: `appuser` (uid 1001)
- `/data` owned by `appuser` — mount PVC here
- `--no-cache-dir` on pip install
- Drop privileges before `CMD`

## CI/CD (GitHub Actions)
- `.github/workflows/ci.yml` — pytest on every push/PR, all branches
- `.github/workflows/cd.yml` — Docker build + push to GHCR on main merge; tags: `sha-<sha>`, `latest`
- Health check: `GET /api/healthz` — DB ping, returns `{"status":"ok"}` or 503

## Registration
- `GET/POST /register` — self-signup, gated by `ALLOW_REGISTRATION=true` env var (default: false)
- Redirect to `/login` when disabled; redirect new user to `/debts` on success
- Validations: username ≥3 chars, password ≥12 chars, confirm match, no duplicate usernames
- Login page shows "Register" link only when `allow_registration=True` passed in context

## Current State (as of 2026-05-01)
- Single-user functional: login, dashboard, add/edit months, plan, remit, settings, AI analysis
- Debt UI: `/debts` list + add, `/debts/{id}/edit`, delete with type-name confirmation
- Income config fully editable in Settings (salary, expenses, phone installment)
- Multi-user: registration via `/register` (gated by ALLOW_REGISTRATION env var)
- First-run init: `scripts/init_db.py` — migrations + admin seed, idempotent
- Dockerfile hardened: non-root user, python:3.13-slim, /data chowned
- Debt sort order: ↑↓ buttons, POST /debts/reorder, sticky Save Order bar
- Admin dashboard: /admin — user list, create, reset password, delete (self-delete blocked)
- Test suite: 31 tests, isolated DB, pytest+httpx+anyio — run `python3 -m pytest tests/ -v`
- Currency: user-selectable debt currency symbol stored in `income_config["currency_symbol"]` + session; set via Settings → Debt Currency; Jinja2 `currency_symbol(request)` global + `| peso` filter both read from session; defaults to ₱
- OFW mode: toggle in Settings → Mode; when off, `rate=1.0`, budget stays in local currency, remit → Budget Planner, income currency select + rate card hidden; `ofw_mode` stored in `income_config` + session
- Empty states: Dashboard and Plan pages show CTA cards when no months/data exist
- Input validation: balance/min_due/payment fields have `type=number min=0` to block negatives
- Login: shows real "Create Account" link when `allow_registration=True`, disabled Coming Soon button otherwise
- Landing page: `/welcome` — public, unauthenticated entry point; authenticated users redirect to `/`; unauthenticated hits on `/` redirect to `/welcome` via `_redirect_login()`
- Progress bar: dashboard shows `pct_paid`/`paid_off`/`peak_debt` — computed from `max(hist_totals)` vs `total_now`
- Confetti: canvas-based, fires on card `done=True` and pct milestones 25/50/75/100; localStorage prevents re-trigger per month
- PDF report: `GET /report/{month}` — clean print-ready HTML, no deps; "Print Report" button opens in new tab from dashboard
- Theme persistence: inline `<script>` in `<head>` on all standalone pages (login, register, landing) applies localStorage theme before render — eliminates flash
- GitHub Actions: CI (pytest) + CD (GHCR push on main merge)
- AI rate limiting: 3 calls/user/day (configurable via AI_DAILY_LIMIT), admins exempt, cached hits free
- asyncpg SSL disabled for Fly.io internal network (connect_args={"ssl": False} in app/db/base.py)
- auto_stop_machines = 'suspend' (not 'stop') — ~1-2s resume vs ~8-10s cold boot
- Data migrated from local SQLite → Fly.io Postgres via scripts/migrate_sqlite_to_pg.py

## Deploy Target
- Platform: Fly.io (`personal-debt-tracker.fly.dev`) — renamed from jayvee-debt-tracker
- Region: Singapore (`sin`)
- Postgres: Fly Unmanaged Postgres (`jayvee-debt-tracker-db`, DB name: `jayvee_debt_tracker`)
- Config: `fly.toml` at project root
- Secrets managed via `flyctl secrets set` (see `fly.env.example`)
- App currently SCALED TO ZERO (intentional) — run `flyctl scale count 1 --app personal-debt-tracker` to restore

## Settings Actions (POST /settings, action= field) — full list
- `rate` — update `sar_to_php` in income_config
- `income` — update `monthly_sar`, `expenses_sar`, `phone.monthly_sar`, `phone.ends`
- `apikey` — save OPENAI_API_KEY to .env via `save_env_value()`
- `password` — verify current, enforce 12-char min, update hash
- `currency` — save `currency_symbol` to income_config + update `request.session["currency_symbol"]`

## Pending Work (next session)
1. **Forgot password** — lowest priority, contact admin covers it for now
2. **Chart theme refresh** — charts don't update colors on theme toggle (minor polish)
3. **Add month overwrite warning** — no warning when re-submitting an existing month
4. **Report page interest column** — currently shows `—` for all rows; needs APR from `data["debts"]` passed into report context