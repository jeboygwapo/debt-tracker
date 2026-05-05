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
    models.py        # User, Debt, Expense, Goal, MonthlyEntry, AiCache
    crud.py          # all DB ops — see Key CRUD Functions below
    adapter.py       # build_data_dict(), debt_name_to_id()
  routes/
    auth.py          # GET/POST /login, GET /logout
    pages.py         # /, /add, /edit/{month}, /plan, /remit, /settings
    api.py           # GET /api/analysis
    debts.py         # GET/POST /debts, /debts/{id}/edit, /debts/{id}/delete, /debts/reorder
    budget.py        # GET/POST /budget, GET /budget/expenses/{id}/edit
    goals.py         # GET/POST /goals, GET /goals/{id}/edit
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
- `Expense` — id, user_id, name, monthly_sar, ends (YYYY-MM, nullable=indefinite), sort_order
- `Goal` — id, user_id, name, target_php, current_php, target_date (YYYY-MM, nullable), monthly_alloc_php, sort_order, created_at

## Key CRUD Functions (app/db/crud.py)
- Users: `get_user_by_username`, `get_user_by_id`, `get_all_users`, `create_user`, `update_user_password`, `update_income_config`, `delete_user`
- Debts: `get_debts(db, user_id)`, `get_debt_by_id(db, debt_id, user_id)`, `create_debt(db, user_id, **kwargs)`, `update_debt(db, debt, **kwargs)`, `delete_debt(db, debt_id, user_id)`, `reorder_debts(db, user_id, ordered_ids)`
- Entries: `get_months`, `get_entries_for_month`, `get_all_entries`, `upsert_entry`, `delete_entries_for_month`
- Expenses: `get_expenses(db, user_id)`, `get_expense_by_id(db, expense_id, user_id)`, `create_expense(db, user_id, **kwargs)`, `update_expense(db, expense, **kwargs)`, `delete_expense(db, expense_id, user_id)`, `reorder_expenses(db, user_id, ordered_ids)`
- Goals: `get_goals(db, user_id)`, `get_goal_by_id(db, goal_id, user_id)`, `create_goal(db, user_id, **kwargs)`, `update_goal(db, goal, **kwargs)`, `delete_goal(db, goal_id, user_id)`, `reorder_goals(db, user_id, ordered_ids)`
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
- Nav active values: `dashboard`, `budget`, `goals`, `debts`, `plan`, `remit`, `settings`. (Phase 1 IA: Add tab dropped, accessed from Dashboard "+ Add Month" button.)
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
- 105 unit+integration tests + 25 smoke + e2e (Playwright). Layers: unit, integration, smoke (`tests/smoke/`), e2e (`tests/e2e/`)
- Markers: `@pytest.mark.smoke`, `@pytest.mark.e2e` registered in `pytest.ini`
- Run unit+integration only: `python3 -m pytest tests/ -m "not e2e and not smoke" -v`
- Run smoke: `python3 -m pytest tests/smoke/ -m smoke -v`
- Run e2e: requires Docker; see `tests/README.md`
- Test DB excluded from Claude context via `.claudeignore`
- **Manual test guide:** `claude_projects/playbooks/TESTER.md` — run before every deploy/demo
- **Pentest protocol:** `claude_projects/playbooks/pentest-protocol.md` + `scripts/pentest.py`

## Do Not Touch
- `alembic/versions/` — never edit manually, generate with `alembic revision`
- Session secret in `.env` (`SECRET_KEY`) — never log or expose

## Security & Hardening
- Login rate limit: `app/ratelimit.py` — 5 attempts/15min per IP, 15min lockout, in-memory dict + threading.Lock
- Session: 8-hour `max_age`, `https_only=True` in production, `same_site=lax`
- Request size: `RequestSizeLimitMiddleware` — 413 if `Content-Length > 1MB`
- `/docs` disabled when `APP_ENV=production`
- Sentry: optional, init via `SENTRY_DSN` env var in `create_app()`, silent if SDK missing

## Settings Actions (POST /settings, action= field)
- `mode` — toggle `ofw_mode` bool in income_config + session
- `apikey` — save OPENAI_API_KEY to .env via `save_env_value()`
- `password` — verify current, enforce 12-char min, update hash
- `currency` — save `currency_symbol` to income_config + update `request.session["currency_symbol"]`
- `strategy` — update `income_config["strategy"]` ∈ `{"avalanche", "snowball", "cash_flow"}`. Single source of truth; dashboard/remit/plan/report all read from here.

**Note:** `income` and `rate` actions removed in Phase 1 (2026-05-04) — now owned by `/budget`. Old POSTs silently fall through to settings render.

## Budget Actions (POST /budget, action= field)
- `income` — update `monthly_sar` (salary) + `expenses_sar` (daily living cap) in income_config
- `rate` — update `sar_to_php` in income_config
- `add_expense` — create Expense(name, monthly_sar, ends, sort_order=highest+1)
- `update_expense` — id, name, monthly_sar, ends
- `delete_expense` — id (ownership-scoped)
- `reorder` — `order` form field = comma-separated ids
- All return 303 redirect to `/budget?msg=...`. Template auto-detects "Invalid"/"not found" prefix → red alert.

## Goals Actions (POST /goals, action= field)
- `add_goal` — create Goal(name, target_php, current_php, monthly_alloc_php, target_date, sort_order)
- `update_goal` — id, name, target_php, current_php, monthly_alloc_php, target_date
- `delete_goal` — id (ownership-scoped)
- `deposit` — id, amount → adds amount to current_php (quick contribution shortcut)
- `reorder` — `order` form field = comma-separated ids
- All return 303 redirect to `/goals?msg=...`. Template auto-detects "Invalid"/"not found" prefix → red alert.

`_goal_progress(goal)` → `{pct, remaining, months_left, on_track, done}`:
- `pct = min(100, current / target * 100)`
- `on_track`: True if `ceil(remaining / monthly_alloc_php) <= months_until_target_date`, else False. None if no target_date.
- `months_left`: from target_date if set, else `ceil(remaining / monthly_alloc_php)` if monthly > 0.

Presets in UI: PAG-IBIG MP2 (₱500,000 / ₱500/mo), Emergency Fund (₱50,000 / ₱2,000/mo).

## Plan Strategy (POST /plan/strategy)
- CSRF-guarded. Validates strategy ∈ `VALID_STRATEGIES`. Persists to `income_config["strategy"]`. 303 redirect to `/plan`.
- GET `/plan?strategy=X` is preview-only — no DB write (CSRF-safe).
- 3 strategies: `avalanche` (highest APR rate first), `snowball` (smallest balance first), `cash_flow` (highest min_due first).

## Planner (`app/services/planner.py`)
- Constants: `EPSILON = 0.5`, `MIN_DUE_PCT = 0.05`, `MIN_DUE_FLOOR_PHP = 500.0`, `PLAN_HORIZON_MONTHS = 120`
- `_snap(x)` — collapses sub-EPSILON floats to 0, rounds others to 2 dp. Use after every balance arithmetic write.
- `_dynamic_min_due(stored_min, balance)` — `max(stored, balance * 5%, ₱500)`, capped at balance.
- `_active_expense_sar(expenses, month)` — sums `monthly_sar` of expenses where `ends is None` or `ends >= month`. End-date inclusive.
- Interest order: payment FIRST, then accrue → `(bal - pay) * (1 + apr/100)`. NOT `bal * (1 + apr/100) - pay`.
- Hybrid cascade: pay fixed loans → pay all CC min_dues → top CC attack + max-1 spillover → fixed-loan prepay (only if `Debt.allow_prepayment=True`).
- `plan_start = month_add(latest, 1)` — auto-derived from latest entry, NOT from config. No more hardcoded `2026-07`.
- Budget formula: `(monthly_sar - expenses_sar - active_expense_sar(month)) × sar_to_php`. `expenses_sar` = unitemized cap; itemized Expense rows subtracted on top.
- `compute_plan` returns `(rows, payoffs, meta)`. `meta = {"truncated", "attack_target", "next_target"}`.
- `allocate_budget` returns `(pay_alloc, cc_priority, attack_target, next_target)`.

## Debt model — `allow_prepayment` field
- `Debt.allow_prepayment: bool` (default False, `server_default=sa.text('false')` for Postgres compat).
- Migration: `alembic/versions/2960f7c8dcc5_add_allow_prepayment_to_debts.py`.
- Force-false for credit cards in `/debts` POST handlers (CC always accept extra anyway).
- When True on a fixed loan, planner cascades surplus into it once all CCs are paid. When False, fixed loan only gets its contractual monthly amount.

## Remit response — bonus fields
- `remit_post` result dict carries `bonus_php = max(0, php - standard)` and `bonus_alloc_to = attack_target` for the green "🎯 Bonus +₱X → ATTACK [card]" callout in `remit.html`.
- `standard` = full plan budget = `(monthly_sar - expenses_sar - active_expense_sar(month)) * rate`. Itemized expenses replace the legacy phone-only subtraction.

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

## Current State (as of 2026-05-04)
- **Phase 1 wealth-tracker pivot shipped**: `/budget` tab combines income config + itemized monthly expenses + disposable card. Income config moved out of Settings. Nav restructured.
- Single-user functional: login, dashboard, add/edit months, plan, remit, budget, settings, AI analysis
- Debt UI: `/debts` list + add, `/debts/{id}/edit`, delete with type-name confirmation, allow_prepayment toggle on non-CC debts
- Budget UI: `/budget` — salary + cap + exchange rate + itemized Expense rows (CRUD + reorder); disposable card with negative-budget warning
- Multi-user: registration via `/register` (gated by ALLOW_REGISTRATION env var)
- First-run init: `scripts/init_db.py` — migrations + admin seed, idempotent
- Dockerfile hardened: non-root user, python:3.13-slim, /data chowned
- Debt sort order: ↑↓ buttons, POST /debts/reorder, sticky Save Order bar
- Admin dashboard: /admin — user list, create, reset password, delete (self-delete blocked)
- Test suite: 120 unit+integration + 27 smoke + e2e (Playwright). Run all non-e2e: `python3 -m pytest tests/ -m "not e2e" -v`
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
- App scaled to 1 (live) — `flyctl scale count 0 --app personal-debt-tracker` to suspend

## Wealth-Tracker Roadmap (approved 2026-05-04)
4-phase pivot from debt-only → personal wealth guide. See `~/.claude/projects/.../memory/project_debt_tracker_roadmap.md`.
- **Phase 1** (DONE 2026-05-04) — `/budget` tab + Expense model + nav restructure
- **Phase 2** (DONE 2026-05-05) — `/goals` tab + Goal model + progress bars + deposit shortcut + 2 presets
- **Phase 3** — `/networth` + Account/AccountSnapshot + AI statement parser (gpt-4o-mini reads PDF/CSV/image, extracts balance, user confirms; original file discarded)
- **Phase 4** (north star) — `/flow` Sankey allocation editor

**Permanent scope guards:** ❌ live bank API sync, ❌ credential scraping, ❌ transaction-level ledger, ❌ trade execution, ❌ multi-currency portfolios beyond PHP+SAR, ❌ original PDF/image storage.

## Pending Work (next session)
1. **Phase 3 — `/networth` + Account/AccountSnapshot + AI statement parser** — gpt-4o-mini reads PDF/CSV/image, extracts balance, user confirms; original file discarded
2. **Multi-tenant isolation audit** — `income_config` JSON + session-keyed currency leak per-user state to globals; needed before Phase 3 ships
3. **`reorder_expenses` / `reorder_goals` cross-tenant index drift** — same pattern as `reorder_debts`; fix together when touched
4. **Forgot password** — lowest priority, contact admin covers it for now