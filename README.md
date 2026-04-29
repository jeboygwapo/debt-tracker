# Debt Tracker

Personal debt tracker for managing credit card payoff, fixed loans, and monthly remittance planning.

## Usage

```bash
python3 app.py
```

Opens browser at http://localhost:5050

## Monthly Workflow (25th of each month)

1. **Settings** → update SAR→PHP rate
2. **Remittance** → enter SAR amount → see card allocation
3. **Dashboard** → Pay This Month table → pay the cards
4. **Add Month** → enter new statement data
5. **Dashboard** → AI Analysis section

See `MONTHLY_INPUT_GUIDE.md` for full reference.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Flask web app (main entry) |
| `tracker.py` | CLI tool (legacy) |
| `menu.py` | Interactive CLI menu (legacy) |
| `debts.json` | Data store — debts, payments, config |
| `MONTHLY_INPUT_GUIDE.md` | Monthly workflow reference |

## Setup

```bash
pip install flask openai
python3 app.py
```

Optional: add OpenAI API key via Settings page for AI analysis.

## Data Not in Repo

- `.env` — OpenAI API key
- `statements-april/` — bank statement PDFs
- `*.csv` — source spreadsheets
- `dashboard.html` — generated export
