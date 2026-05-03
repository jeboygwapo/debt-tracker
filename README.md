# Debt Tracker

Personal debt repayment tracker for managing credit card payoff, fixed loans, and monthly budget planning. Supports OFW context (income in foreign currency, debts in local currency with exchange rate conversion) or local-only mode.

**Live:** https://personal-debt-tracker.fly.dev

---

## Features

- **Dashboard** — total debt, credit card balance, monthly interest, debt-free target, avalanche payment plan
- **Balance Trend & Breakdown** — Chart.js line/bar/donut charts with projected payoff curve
- **Budget / Remittance Planner** — enter amount available, see allocation across all cards
- **Avalanche payoff engine** — minimums on all, extra cash attacks highest-APR card first
- **OFW mode** — toggle in Settings; converts income currency → debt currency at saved rate; when off, budget stays in local currency with no conversion
- **Empty states** — all pages guide new users with CTAs when no data exists yet
- **Payoff progress bar** — dashboard shows % paid off from peak debt with milestone messages
- **Confetti & milestone toasts** — celebrates card payoffs and 25/50/75/100% progress milestones
- **Print / PDF report** — `/report/{month}` renders a clean print-ready page; save as PDF via browser
- **AI Analysis** — optional OpenAI `gpt-4o-mini` debt summary; 3 calls/day per user (admins exempt, cached hits free)
- **Public landing page** — `/welcome` for unauthenticated visitors with feature overview
- **Multi-user** — admin dashboard for user management; self-signup gated by `ALLOW_REGISTRATION`
- **Weekly DB backup** — GitHub Actions exports all data to CSV artifacts every Sunday

---

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (async), Alembic
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Frontend**: Jinja2, vanilla JS, Chart.js, Tailwind (CDN)
- **Auth**: Starlette `SessionMiddleware`, bcrypt
- **Deploy**: Docker + Fly.io (Singapore region)

---

## Local Development

### Prerequisites
- Python 3.13
- Docker (for local Postgres)

### Setup

```bash
git clone https://github.com/jeboygwapo/debt-tracker.git
cd debt-tracker

# Create virtualenv and install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill in env vars
cp fly.env.example .env
# Set at minimum: SECRET_KEY (generate below), DATABASE_URL

# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Start local Postgres

```bash
# Set DB vars in .env first (DB_USER, DB_PASSWORD, DB_NAME)
docker compose up -d
```

### Init database and seed admin

```bash
python scripts/init_db.py
```

Runs Alembic migrations, prompts for admin username + password if no users exist. Safe to re-run.

### Run the app

```bash
uvicorn main:app --reload --port 5050
```

App runs at http://localhost:5050.

### Run tests

```bash
python -m pytest tests/ -v
```

Uses an isolated SQLite test DB — no Docker or Postgres required. 41 tests across auth, pages, debts, admin, and AI rate limiting.

---

## Environment Variables

See `fly.env.example` for the full template with descriptions.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | — | Session signing key |
| `DATABASE_URL` | Yes | — | SQLAlchemy async URL, e.g. `postgresql+asyncpg://user:pass@host/db` |
| `APP_ENV` | No | `development` | Set `production` to enforce SECRET_KEY check |
| `ALLOW_REGISTRATION` | No | `false` | Set `true` to enable self-signup via `/register` |
| `OPENAI_API_KEY` | No | — | Enables AI debt analysis |
| `AI_DAILY_LIMIT` | No | `3` | Max AI calls per non-admin user per day |
| `SENTRY_DSN` | No | — | Sentry error monitoring DSN (leave blank to disable) |
| `DATA_DIR` | No | project root | SQLite DB and `.env` location (local only) |
| `PORT` | No | `5050` | HTTP port |
| `DB_USER` | Docker only | — | Postgres username (docker-compose) |
| `DB_PASSWORD` | Docker only | — | Postgres password (docker-compose) |
| `DB_NAME` | Docker only | — | Postgres database name (docker-compose) |

---

## Deploy (Fly.io)

The app deploys from `Dockerfile` via `flyctl`. No image registry involved.

### First deploy

```bash
flyctl auth login
flyctl launch --no-deploy   # generates fly.toml (already committed — skip overwrite)

# Set required secrets
flyctl secrets set SECRET_KEY=<generated>
flyctl secrets set DATABASE_URL=postgresql+asyncpg://user:pass@host/db
flyctl secrets set APP_ENV=production

# Optional
flyctl secrets set OPENAI_API_KEY=sk-...
flyctl secrets set AI_DAILY_LIMIT=3

flyctl deploy
```

### Subsequent deploys

```bash
flyctl deploy --app personal-debt-tracker
```

Or push to `main` — GitHub Actions deploys automatically after CI passes.

### Scale up (app suspends when idle)

```bash
flyctl scale count 1 --app personal-debt-tracker
```

---

## CI/CD (GitHub Actions)

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | Every push / PR | Runs `pytest` (41 tests) |
| `deploy-fly.yml` | After CI passes on `main` | Runs `flyctl deploy --remote-only` |
| `backup.yml` | Every Sunday 2AM UTC + manual | Exports DB to CSV, uploads as artifact (90-day retention) |

No Docker image registry (GHCR) is used. Fly.io builds the image remotely from `Dockerfile`.

### Required GitHub Secrets

| Secret | Used by |
|---|---|
| `FLY_API_TOKEN` | `deploy-fly.yml`, `backup.yml` |
| `SECRET_KEY` | `backup.yml` (DB export) |
| `DB_PASSWORD` | `backup.yml` (proxy tunnel to Fly Postgres) |

---

## Settings Reference

| Section | What it controls |
|---|---|
| Mode | OFW mode on/off (exchange rate conversion) |
| Exchange Rate | Income → debt currency rate |
| Currency | Income currency code + debt currency symbol |
| Income Config | Monthly salary, expenses, phone installment |
| OpenAI API Key | Enables AI analysis (stored in `.env` on server) |
| Change Password | Min 12 characters |

---

## Monthly Usage

See [MONTHLY_INPUT_GUIDE.md](MONTHLY_INPUT_GUIDE.md) for the monthly data entry workflow.
