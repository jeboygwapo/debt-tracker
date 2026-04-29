# Monthly Guide — Every 25th

## Full Workflow (in order)

```bash
python3 app.py   # ← only command you need to remember
```

Opens browser automatically at http://localhost:5050

**Monthly steps (all done in browser):**
1. Settings → update SAR→PHP rate (check Wise/Western Union first)
2. Remittance → enter SAR amount → see exact allocation per card
3. Dashboard → "Pay This Month" table → pay the cards
4. Add Month → enter new statement data after paying
5. Dashboard → AI Analysis section shows advice automatically

---

## What to grab from each statement (3 fields only)

| Field | Where to find |
|-------|--------------|
| **Balance** | "Total Amount Due" / "Total Balance Due" |
| **Minimum Due** | "Minimum Payment Due" |
| **Due Date** | "Payment Due Date" |

Payment + Paid On → fill in AFTER you pay.

---

## Per bank — where to look

| Card | Statement Name | Location |
|------|---------------|----------|
| UB Gold (8235) | UnionBank CashBack Gold MasterCard | Top right summary box |
| UB Platinum (7749) | UnionBank Rewards Platinum Visa | Top right summary box |
| UB Citi (1595) | UnionBank Rewards Platinum Visa | Top right summary box |
| UB SNR (7487) | UnionBank S&R Visa Platinum | Top right summary box |
| BPI Blue (4029) | BPI Credit Cards SOA | Header summary box (page 3) |
| RCBC Gold (4009) | RCBC Statement of Account | Account Summary box |

---

## All commands

```bash
python3 tracker.py                      # summary (latest month)
python3 tracker.py summary              # summary (latest month)
python3 tracker.py summary 2026-03      # specific month
python3 tracker.py setrate              # update live SAR→PHP rate
python3 tracker.py remit 5650           # plan for X SAR sent this month
python3 tracker.py budget 84750         # plan for X PHP budget
python3 tracker.py export               # generate dashboard.html
python3 tracker.py plan avalanche       # full payoff timeline
python3 tracker.py plan snowball        # payoff timeline (snowball)
python3 tracker.py strategy avalanche   # priority order
python3 tracker.py add                  # add new month data
python3 tracker.py history              # balance trend
python3 tracker.py analyze              # AI analysis (needs OpenAI key)
python3 tracker.py setkey sk-...        # save OpenAI API key
python3 tracker.py help                 # this list
```

---

## Payment rules (saved in debts.json)

| Debt | Rule |
|------|------|
| Mama Balance | ₱26,066/month until balance ≤ ₱20,000 → drops to ₱10,000/month |
| Eastwest Loan | Fixed ₱3,197.45/month until Jan 2028 |
| Credit cards | Minimums on all, everything extra → highest interest card first (Avalanche) |

---

## Income config (debts.json)

| Field | Value |
|-------|-------|
| Monthly salary | 13,850 SAR |
| Saudi expenses | 7,000 SAR (includes ₱1,500 SAR emergency fund) |
| Phone installment | 1,200 SAR (ends July 2026) |
| Standard remittance | 5,650 SAR / month |
| SAR→PHP rate | update monthly via `setrate` |

---

## Attack card order (Avalanche — highest interest first)

1. UB Platinum Visa (7749) — 3%/mo, ₱160k
2. UB SNR (7487) — 3%/mo, ₱151k
3. RCBC Gold JCB (4009) — 3%/mo, ₱75k
4. BPI Blue CC (4029) — 3%/mo, ₱69k
5. UB Citi (1595) — 3%/mo, ₱45k
6. UB Gold (8235) — 2%/mo, ₱48k

**Target: ALL CREDIT CARDS GONE by March 2027. Full debt-free April 2028.**
