# Debt Tracker — Manual Test Guide

Run this before any deploy or demo. Covers every user-facing flow.

**Prerequisites**
- App running locally (`uvicorn main:app --reload --port 5050`) or on Fly.io
- At least 1 admin user seeded via `python scripts/init_db.py`
- Local: `APP_ENV=development` (no HTTPS requirement)

---

## 1. Authentication

### 1.1 Login
- [ ] Go to `/welcome` → landing page loads, theme matches last used
- [ ] Click "Sign In" → `/login` opens
- [ ] Submit empty form → stays on login, no crash
- [ ] Submit wrong credentials → error shows remaining attempts count
- [ ] Submit wrong credentials 5× → locked out message shows, countdown in minutes
- [ ] Wait out lockout OR restart app → login works again
- [ ] Submit correct credentials → redirected to `/`

### 1.2 Session
- [ ] Log in → close browser tab → reopen → still logged in (session persists)
- [ ] Log out → `/logout` → redirected to `/login`
- [ ] Access `/` while logged out → redirected to `/welcome`
- [ ] Access `/settings` while logged out → redirected to `/welcome`

### 1.3 Registration (when ALLOW_REGISTRATION=true)
- [ ] `/register` shows form
- [ ] Username < 3 chars → error
- [ ] Password < 12 chars → error
- [ ] Passwords don't match → error
- [ ] Duplicate username → error
- [ ] Valid form → account created, redirected to `/debts`

---

## 2. Debt Setup

### 2.1 Add Debt (`/debts`)
- [ ] Empty state shows icon + "Add Your First Debt" button
- [ ] Click button → inline form appears
- [ ] Submit without name → stays on form, no crash
- [ ] Add credit card (name, APR, type=Credit Card) → appears in list with red badge
- [ ] Add personal loan (type=Loan) → yellow badge
- [ ] Add fixed loan (check "Fixed monthly payment") → fixed fields appear
  - Set monthly amount + end date → saved correctly
  - Threshold fields show correct placeholder text

### 2.2 Edit & Delete
- [ ] Click "Edit" on a debt → edit form loads with current values
- [ ] Change APR → saved
- [ ] Delete → type-name confirmation required → debt removed, entries gone

### 2.3 Reorder
- [ ] Click ↑ / ↓ → row moves → "Save Order" bar appears
- [ ] Click "Cancel" → order reverts without saving
- [ ] Click "Save Order" → order persists on reload

---

## 3. Monthly Data Entry

### 3.1 Add Month (`/add`)
- [ ] No debts → form shows 0 cards (add debts first)
- [ ] With debts → Statement tab shows all cards
- [ ] Enter balance, min due, due date for each card
- [ ] Switch to Payments tab → shows same cards
- [ ] Enter payment amounts → "= Min" button fills minimum
- [ ] "Today" button fills today's date in Paid On
- [ ] Submit → success summary appears below with allocation plan
- [ ] **Overwrite test**: submit same month again → yellow warning "already existed — data updated"

### 3.2 Validation
- [ ] Try entering negative balance → browser blocks (min=0)
- [ ] Try entering negative payment → browser blocks (min=0)

### 3.3 Edit Month (`/edit/{month}`)
- [ ] From dashboard → "✏️ Edit" → edit form loads with saved values
- [ ] Change a payment → save → redirected back with "Saved" message
- [ ] Access `/edit/9999-99` → redirected to dashboard (invalid month)

---

## 4. Dashboard (`/`)

### 4.1 Empty State
- [ ] No months entered → empty state card shows with CTAs (no blank page)
- [ ] "Add This Month's Data" CTA links to `/add`
- [ ] "Set Up My Debts" links to `/debts`

### 4.2 With Data
- [ ] Summary cards show: Total Debt, Credit Cards, Interest/Month, Debt-Free Target, Monthly Budget
- [ ] OFW mode ON → exchange rate card visible
- [ ] OFW mode OFF → exchange rate card hidden
- [ ] "Debt-Free Target" shows date, not "—", when data exists
- [ ] Progress bar visible with % paid from peak
- [ ] Motivational message appears at 25% / 50% / 75% thresholds

### 4.3 Charts
- [ ] Balance Trend chart renders (line by default)
- [ ] Toggle Line → Bar → chart switches
- [ ] Breakdown chart renders (donut by default)
- [ ] Toggle Donut → Pie → Bar → each works
- [ ] Toggle theme → charts immediately re-render in correct colors (no stale palette)
- [ ] Chart preference saved — survives page reload

### 4.4 Payment Plan Table
- [ ] ATTACK card highlighted
- [ ] Fixed loans shown as "Fixed"
- [ ] Extra payment shown in green where applicable

### 4.5 Card Status Table
- [ ] Paid cards show green amount
- [ ] Under-minimum payments show red "⚠ under min"
- [ ] DONE cards show "DONE ✓" spanning all columns

### 4.6 Month Navigation
- [ ] Month selector dropdown shows all months, latest marked ★
- [ ] Select older month → dashboard shows that month's data
- [ ] "✏️ Edit" updates to selected month
- [ ] "🖨️ Print Report" opens report for selected month in new tab

### 4.7 Confetti
- [ ] First time a card reaches ₱0 → confetti fires + toast "Card Paid Off!"
- [ ] Reload → no duplicate confetti (localStorage flag)
- [ ] First time pct_paid ≥ 25% → milestone toast fires
- [ ] Reload → no duplicate milestone confetti

---

## 5. Budget / Remittance Planner (`/remit`)

### 5.1 OFW Mode ON
- [ ] Page title: "Remittance Planner"
- [ ] Shows "Amount (SAR)" input and current rate
- [ ] Enter amount → calculate → shows PHP received, allocation table
- [ ] Extra vs plan shown in green; short shown in red

### 5.2 OFW Mode OFF
- [ ] Page title: "Budget Planner"
- [ ] Rate input hidden
- [ ] Shows "Amount (local currency)" input
- [ ] Enter amount → calculate → allocation table in local currency

---

## 6. Payoff Plan (`/plan`)

### 6.1 Empty State
- [ ] No data → empty state with icon + "Add This Month's Data" CTA

### 6.2 With Data
- [ ] Avalanche button active by default
- [ ] Card payoff date grid shows each debt's projected payoff month
- [ ] Switch to Snowball → payoff order changes
- [ ] Month-by-month table shows budget, total debt, paid-off cards

---

## 7. Print Report (`/report/{month}`)

- [ ] Click "🖨️ Print Report" from dashboard → opens in new tab
- [ ] Dark header with month, username, debt-free date
- [ ] Progress bar matches dashboard
- [ ] Summary grid: total debt, interest, budget, exchange rate (if OFW), debt-free target
- [ ] Payment Allocation table: ATTACK badge on highest-APR card
- [ ] Card Status table: interest column shows actual amounts (not "—")
- [ ] "Print / Save PDF" button triggers browser print dialog
- [ ] "← Back to Dashboard" link works
- [ ] Print preview is clean (nav, buttons hidden via `@media print`)

---

## 8. Settings (`/settings`)

### 8.1 Mode Toggle
- [ ] OFW checkbox unchecked → rate section hidden, income currency hidden, budget stays in local currency
- [ ] OFW checkbox checked → rate section visible, income currency visible
- [ ] Toggle auto-submits (no Save button needed)

### 8.2 Exchange Rate
- [ ] Update rate → success message shows new rate
- [ ] Invalid rate (text) → stays, no crash

### 8.3 Currency
- [ ] Change currency symbol → all peso values update site-wide
- [ ] OFW ON: income currency selector visible; OFW OFF: hidden

### 8.4 Income Config
- [ ] Update salary, expenses → "Net available" preview updates
- [ ] OFW ON: preview shows conversion; OFW OFF: shows only local amount
- [ ] Phone installment: fill amount + end date → budget reduces while date active

### 8.5 Password
- [ ] Wrong current password → error
- [ ] New password < 12 chars → error
- [ ] Passwords don't match → error
- [ ] Valid change → success, can log in with new password

### 8.6 OpenAI Key
- [ ] Paste key → saved → AI section appears on dashboard
- [ ] Invalid key → AI section shows error gracefully (not a crash)

---

## 9. AI Analysis (if OPENAI_API_KEY set)

- [ ] Dashboard shows "🤖 AI Analysis" section
- [ ] On load → "Loading analysis…" then analysis renders
- [ ] "↺ Refresh" → re-fetches (uses cache if data unchanged)
- [ ] "fresh from OpenAI" label on new fetch; "cached" label on cache hit
- [ ] 3 force-refreshes → 4th returns rate limit error (non-admin)
- [ ] Admin user → no rate limit

---

## 10. Admin (`/admin`)

- [ ] Non-admin → 403
- [ ] Admin → user list shows all users
- [ ] Create user → appears in list
- [ ] Reset password → user can log in with new password
- [ ] Delete user → removed (cannot delete self)

---

## 11. Security Checks

- [ ] POST to `/settings` without CSRF token → 403
- [ ] POST to `/add` without CSRF token → 403
- [ ] Direct URL `/admin` as non-admin → 403
- [ ] `/api/analysis` without login → 401 JSON response
- [ ] Access another user's data directly (by changing month in URL) → only own data shown

---

## 12. Theme & Responsiveness

- [ ] Dark mode default on fresh session
- [ ] Toggle to light → persists on login page, dashboard, landing page (no flash)
- [ ] Resize to mobile width → nav collapses to hamburger
- [ ] All tables collapse to card layout on mobile
- [ ] Forms wrap correctly on small screens

---

## 13. Automated Tests

```bash
python3 -m pytest tests/ -v
```

Expected: **41 passed, 0 failed**

Test files:
- `tests/test_auth.py` — login, logout, register, redirect
- `tests/test_pages.py` — dashboard, add/edit month, remit, settings, AI, health check
- `tests/test_debts.py` — CRUD, reorder
- `tests/test_admin.py` — admin user management
