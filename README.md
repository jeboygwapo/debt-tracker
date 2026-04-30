# Debt Tracker

Personal debt repayment tracker for managing credit card payoff, fixed loans, and monthly remittance planning. Built for an OFW context: income in SAR, debts in PHP, with avalanche/snowball payoff projections and optional AI analysis.

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy (async), Alembic
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Frontend**: Jinja2, vanilla JS, Chart.js, Tailwind (CDN)
- **Auth**: Starlette `SessionMiddleware`, bcrypt
- **Infra**: Docker, GitHub Actions, GHCR

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
| `SECRET_KEY` | Yes | Session signing key — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Yes | SQLAlchemy async URL, e.g. `postgresql+asyncpg://user:pass@host/db` |
| `DB_USER` | Yes (Docker) | Postgres username |
| `DB_PASSWORD` | Yes (Docker) | Postgres password |
| `DB_NAME` | Yes (Docker) | Postgres database name |
| `APP_ENV` | No | `production` or `development` (default: `development`) |
| `ALLOW_REGISTRATION` | No | `true` to enable self-signup (default: `false`) |
| `OPENAI_API_KEY` | No | Enables AI debt analysis via `gpt-4o-mini` |
| `PORT` | No | HTTP port (default: `5050`) |

See `.env.example` for a template.

## Running Tests

```bash
python -m pytest tests/ -v
```

Uses an isolated SQLite test DB — no external dependencies required.

## Deploy to Fly.io

Install flyctl, then:

```
flyctl auth login
flyctl launch --no-deploy  # first time only
flyctl postgres create      # attach managed Postgres
flyctl secrets set SECRET_KEY=<generated> APP_ENV=production DATABASE_URL=<postgres-url>
flyctl deploy
```

See `fly.env.example` for the full list of secrets to set.

## CI/CD

- **CI** (`.github/workflows/ci.yml`): runs `pytest` on every push and pull request, all branches.
- **CD** (`.github/workflows/cd.yml`): builds Docker image and pushes to GHCR on merge to `main`. Tags: `sha-<sha>`, `latest`.
- **Fly deploy** (`.github/workflows/deploy-fly.yml`): deploys to `jayvee-debt-tracker.fly.dev` after CI passes on `main`.

## Monthly Usage

See [MONTHLY_INPUT_GUIDE.md](MONTHLY_INPUT_GUIDE.md) for the monthly data entry workflow.
