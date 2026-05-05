# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/) — MAJOR.MINOR.PATCH.

---

## [Unreleased]
> Work in progress — not yet deployed.

---

## [0.3.1] — 2026-05-05

### Security
- Session display preferences (`currency_symbol`, `income_currency`, `ofw_mode`) now sync from DB on every authenticated request. Previously only seeded at login — stale values persisted across sessions until re-login.
- `reorder_debts`, `reorder_expenses`, `reorder_goals` now pre-validate that all submitted IDs belong to the requesting user before issuing UPDATE statements. Crafted payloads containing foreign IDs could previously cause sort_order gaps.

### Added
- `VERSION` file at project root — version now shown correctly in footer instead of "dev".
- `scripts/notify_users.py` — reusable post-deploy script to broadcast system notifications to all users.

### Changed
- `app/config.py` reads version from `APP_VERSION` env var first, falls back to `VERSION` file, then "dev".

---

## [0.3.0] — 2026-05-05

### Added
- **`/goals` tab** (Phase 2 wealth-tracker pivot).
- `Goal` model: `name`, `target_php`, `current_php`, `monthly_alloc_php`, `target_date` (YYYY-MM), `sort_order`.
- Progress bar per goal with "On track" / "Behind" / "No target date" status badge.
- `_goal_progress()` helper: computes `pct`, `remaining`, `months_left`, `on_track`, `done`.
- Quick deposit modal — add to current balance without opening edit page.
- Reorder goals ↑↓ with sticky Save Order bar.
- Two presets: PAG-IBIG MP2 (₱500,000 / ₱500/mo) and Emergency Fund (₱50,000 / ₱2,000/mo).
- Goals nav link between Budget and My Cards.
- 21 tests (8 unit + 13 integration).
- Alembic migration: `12d1c3e1777b_add_goals_table`.

---

## [0.2.0] — 2026-05-04

### Added
- **`/budget` tab** (Phase 1 wealth-tracker pivot) — combines income config + itemized expenses + live disposable card.
- `Expense` model: `name`, `monthly_sar`, `ends` (YYYY-MM, inclusive end-date), `sort_order`.
- `_active_expense_sar(expenses, month)` — sums only non-expired expenses for a given month.
- Budget Actions: `income`, `rate`, `add_expense`, `update_expense`, `delete_expense`, `reorder`.
- Disposable card: monospace breakdown `Salary − Cap − itemized expenses → Net → PHP`. Red banner if negative.
- Expense CRUD table with reorder ↑↓, edit, delete.
- Budget nav link (replaced Add tab; Add Month moved to Dashboard header button).
- `scripts/migrate_phone_to_expenses.py` — one-shot migration of legacy `income_config.phone` → Expense row.
- 21 tests for budget routes and planner expense aggregation.
- Alembic migration: `d9970f90e2e6_add_expenses_table`.

### Changed
- `income` and `rate` settings actions removed from `/settings` POST — now owned by `/budget`.
- Settings page shows redirect notice to Budget tab for income config.
- Dashboard shows "+ Add Month" button in header (compensates for dropped Add nav tab).
- Planner `plan_start` auto-derived from `month_add(latest, 1)` — no longer hardcoded.
- Budget formula: `(monthly_sar − expenses_sar − active_expense_sar) × rate`. Itemized expenses replace legacy phone-only subtraction.

### Fixed
- Plan page months no longer start from hardcoded July — plan now starts the month after the latest data entry.

---

## [0.1.0] — 2026-04-29

### Added
- Initial release — personal debt repayment tracker for OFW context (SAR income, PHP debts).
- **Dashboard** — total debt, CC balance, monthly interest, debt-free projection, avalanche payment table.
- **Balance Trend & Breakdown** — Chart.js line/bar/donut charts with projected payoff curve.
- **Remittance Planner** (`/remit`) — enter SAR amount, see allocation across all cards. Bonus callout for extra above standard.
- **Payoff Plan** (`/plan`) — avalanche, snowball, cash_flow strategies. Preview via query param (CSRF-safe).
- **My Cards** (`/debts`) — debt CRUD with type (credit_card / personal_loan / other), APR, fixed payment config, `allow_prepayment` toggle, sort order.
- **Settings** — OFW mode toggle, currency symbol, income currency, strategy, OpenAI API key, change password.
- **Add / Edit Month** — upsert monthly statement data per debt: balance, min_due, payment, due_date, paid_on, note.
- **PDF Report** (`/report/{month}`) — clean print-ready page for any month.
- **AI Analysis** — optional `gpt-4o-mini` debt summary; 3 calls/day per user (admins exempt, cached hits free).
- **Avalanche engine** — minimums on all debts, extra attacks highest-APR card. Hybrid: fixed loans → CC minimums → attack + spillover → optional loan prepayment.
- **OFW mode** — SAR → PHP conversion at saved rate. Toggle hides rate card when off.
- **Multi-user** — admin dashboard (`/admin`): user list, create, reset password, delete. Self-signup gated by `ALLOW_REGISTRATION`.
- **Notifications** — admin broadcast; bell badge in nav; mark-all-read.
- **Public landing page** (`/welcome`) — unauthenticated entry with feature overview.
- **Empty states** — Dashboard and Plan guide new users with CTAs.
- **Progress bar** — % paid off from peak debt with milestone messages.
- **Confetti & milestone toasts** — fires on card payoff and 25/50/75/100% milestones; localStorage prevents re-trigger.
- **Login rate limiting** — 5 attempts / 15-min lockout per IP.
- **CSRF protection** — all POST forms require signed token.
- **Session security** — 8-hour max-age, HTTPS-only in production, same-site lax.
- **Request size limit** — 1 MB cap, returns 413.
- **CSP headers** — `SecurityHeadersMiddleware` on all responses.
- **Sentry** — optional error monitoring via `SENTRY_DSN`.
- **Weekly DB backup** — GitHub Actions exports all data to CSV artifacts every Sunday.
- **CI/CD** — GitHub Actions: pytest on every push/PR; Docker build → GHCR → Fly.io deploy on main merge with auto-rollback on failed health check.
- **Docker hardening** — non-root user (`appuser` uid 1001), `python:3.13-slim`, `/data` volume.
- Deploy target: Fly.io (`personal-debt-tracker.fly.dev`), Singapore region, Fly Postgres.

---

[Unreleased]: https://github.com/jeboygwapo/debt-tracker/compare/v0.3.1...HEAD
[0.3.1]: https://github.com/jeboygwapo/debt-tracker/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/jeboygwapo/debt-tracker/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jeboygwapo/debt-tracker/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jeboygwapo/debt-tracker/releases/tag/v0.1.0
