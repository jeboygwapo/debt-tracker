# Debt Tracker

Personal debt repayment tracker for managing credit card payoff, fixed loans, and monthly budget/remittance planning. Supports OFW context (income in foreign currency, debts in local currency) or local-only mode with no exchange rate conversion.

Live at: **https://personal-debt-tracker.fly.dev**

## Features

- **Dashboard** — total debt, credit card balance, monthly interest, debt-free target, avalanche payment plan
- **Balance Trend & Breakdown** — Chart.js line/bar/donut with projected payoff curve
- **Budget / Remittance Planner** — enter amount sent, see allocation across all cards
- **Avalanche payoff engine** — minimums on all cards, extra cash attacks highest-APR first
- **OFW mode** — toggle in Settings; when on, converts income currency → debt currency using saved exchange rate; when off, budget stays in local currency
- **AI Analysis** — optional OpenAI `gpt-4o-mini` debt summary (3 calls/day per user, admins exempt)
- **Multi-user** — admin dashboard for user management; self-signup gated by `ALLOW_REGISTRATION`
- **Weekly DB backup** — GitHub Actions exports CSV to workflow artifacts every Sunday

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (async), Alembic
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Frontend**: Jinja2, vanilla JS, Chart.js, Tailwind (CDN)
- **Auth**: Starlette `SessionMiddleware`, bcrypt
- **Infra**: Docker, GitHub Actions, GHCR, Fly.io

## Quick Start

```bash
git clone <repo-url>
cd debt-tracker
cp .env.example .env        # fill in SECRET_KEY and DB creds
docker compose up -d
docker compose exec app python scripts/init_db.py   # runs migrations + seeds admin
```

App runs at http://localhost:5050.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Session signing key — `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Yes | SQLAlchemy async URL, e.g. `postgresql+asyncpg://user:pass@host/db` |
| `DB_USER` | Yes (Docker) | Postgres username |
| `DB_PASSWORD` | Yes (Docker) | Postgres password |
| `DB_NAME` | Yes (Docker) | Postgres database name |
| `APP_ENV` | No | `production` or `development` (default: `development`) |
| `ALLOW_REGISTRATION` | No | `true` to enable self-signup (default: `false`) |
| `OPENAI_API_KEY` | No | Enables AI debt analysis via `gpt-4o-mini` |
| `AI_DAILY_LIMIT` | No | Max AI calls per user per day (default: `3`; admins exempt) |
| `PORT` | No | HTTP port (default: `5050`) |

See `fly.env.example` for the full list of Fly.io secrets.

## Running Tests

```bash
python -m pytest tests/ -v
```

Uses an isolated SQLite test DB — no external dependencies required. 41 tests covering auth, pages, debts CRUD, admin, and AI rate limiting.

## Deploy to Fly.io

```bash
flyctl auth login
flyctl launch --no-deploy          # first time only
flyctl secrets set SECRET_KEY=<key> APP_ENV=production DATABASE_URL=<postgres-url>
flyctl deploy
```

See `fly.env.example` for the full list of secrets to configure.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): runs `pytest` on every push and pull request.
- **CD** (`.github/workflows/cd.yml`): builds Docker image, pushes to GHCR on merge to `main`. Tags: `sha-<sha>`, `latest`.
- **Deploy** (`.github/workflows/deploy-fly.yml`): deploys to Fly.io after CI passes on `main`.
- **Backup** (`.github/workflows/backup.yml`): exports DB to CSV artifacts every Sunday at 2AM UTC via `flyctl proxy` tunnel.

## Settings

| Section | What it does |
|---|---|
| Mode | Toggle OFW mode (exchange rate on/off) |
| Exchange Rate | Update income → debt currency rate |
| Currency | Set income currency and debt currency symbol |
| Income Config | Monthly salary, expenses, phone installment |
| OpenAI API Key | Enable AI analysis |
| Change Password | Min 12 characters |

## Monthly Usage

See [MONTHLY_INPUT_GUIDE.md](MONTHLY_INPUT_GUIDE.md) for the monthly data entry workflow.
