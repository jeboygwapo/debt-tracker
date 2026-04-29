#!/usr/bin/env python3
"""
Debt Tracker Web App — run: python3 app.py
Opens browser automatically at http://localhost:5050
"""

import json, os, webbrowser, threading
from pathlib import Path
from datetime import date
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, jsonify, session

_data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
DATA_FILE = _data_dir / "debts.json"
ENV_FILE  = _data_dir / ".env"
app = Flask(__name__)

# ── auth ───────────────────────────────────────────────────────────────────

def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

LOGIN_TMPL = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Debt Tracker — Login</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#1e293b;border-radius:12px;padding:2.5rem;width:100%;max-width:360px;box-shadow:0 8px 32px rgba(0,0,0,.4)}
h2{font-size:1.4rem;margin-bottom:1.5rem;color:#f1f5f9;text-align:center}
label{display:block;font-size:.8rem;color:#94a3b8;margin-bottom:.4rem}
input{width:100%;padding:.65rem .9rem;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#f1f5f9;font-size:.95rem;margin-bottom:1rem}
input:focus{outline:none;border-color:#6366f1}
button{width:100%;padding:.75rem;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:1rem;cursor:pointer;font-weight:600}
button:hover{background:#4f46e5}
.err{color:#f87171;font-size:.85rem;margin-bottom:1rem;text-align:center}
</style>
</head>
<body>
<div class="card">
  <h2>💳 Debt Tracker</h2>
  {% if error %}<p class="err">{{ error }}</p>{% endif %}
  <form method="POST">
    <label>Username</label>
    <input name="username" type="text" autofocus autocomplete="username">
    <label>Password</label>
    <input name="password" type="password" autocomplete="current-password">
    <button type="submit">Sign In</button>
  </form>
</div>
</body>
</html>"""

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = os.environ.get("APP_USER", "admin")
        pwd  = os.environ.get("APP_PASSWORD", "changeme")
        if request.form["username"] == user and request.form["password"] == pwd:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Invalid username or password."
    return render_template_string(LOGIN_TMPL, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ── helpers ────────────────────────────────────────────────────────────────

def load():
    with open(DATA_FILE) as f:
        return json.load(f)

def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def latest_month(data):
    months = sorted(data["months"].keys())
    return months[-1] if months else None

def fp(v):
    return f"₱{v:,.2f}"

def month_add(ym, n):
    y, m = int(ym[:4]), int(ym[5:])
    m += n; y += (m-1)//12; m = (m-1)%12+1
    return f"{y}-{m:02d}"

def month_diff(a, b):
    ya,ma=int(a[:4]),int(a[5:]); yb,mb=int(b[:4]),int(b[5:])
    return (yb-ya)*12+(mb-ma)

def compute_plan(data, strategy="avalanche"):
    cfg        = data.get("income_config", {})
    fixed_pmts = data.get("fixed_payments", {})
    sar_php    = cfg.get("sar_to_php", 15.0)
    plan_start = cfg.get("plan_start", "2026-07")
    phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
    phone_sar  = cfg.get("phone", {}).get("monthly_sar", 0)
    base_sar   = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
    latest     = latest_month(data)
    entries    = data["months"].get(latest, {})

    balances = {n: (e.get("balance",0) or 0) for n,e in entries.items()}
    gap = month_diff(latest, plan_start)
    for _ in range(gap):
        for n, e in entries.items():
            bal = balances[n]
            if bal <= 0: continue
            mn    = e.get("min_due",0) or 0
            dtype = data["debts"].get(n,{}).get("type","credit_card")
            apr   = data["debts"].get(n,{}).get("apr_monthly_pct",0.0)
            balances[n] = max(0, bal*(1+apr/100)-mn if dtype=="credit_card" else bal-mn)

    sim      = {k:v for k,v in balances.items() if v>0}
    cc_names = [n for n in sim if data["debts"].get(n,{}).get("type")=="credit_card"]
    payoffs  = {}
    rows     = []
    m        = plan_start

    for _ in range(120):
        if all(v<=0 for v in sim.values()): break
        phone_active = m <= phone_ends
        budget = (base_sar-(phone_sar if phone_active else 0))*sar_php
        remaining = budget
        allocs = {}

        for n in list(sim):
            if sim[n]<=0 or n not in fixed_pmts: continue
            fp_cfg    = fixed_pmts[n]
            threshold = fp_cfg.get("reduced_threshold",0)
            rate      = fp_cfg.get("reduced_monthly",fp_cfg["monthly"]) if (threshold and sim[n]<=threshold) else fp_cfg["monthly"]
            pay = min(rate, sim[n], remaining)
            allocs[n] = pay; remaining -= pay

        cc_data = [(n,sim[n],sim[n]*data["debts"].get(n,{}).get("apr_monthly_pct",3)/100)
                   for n in cc_names if sim[n]>0]
        cc_data.sort(key=lambda x: -x[2] if strategy=="avalanche" else x[1])

        for n,bal,_ in cc_data:
            mn  = entries.get(n,{}).get("min_due",0) or 0
            pay = min(mn, bal, remaining)
            allocs[n] = allocs.get(n,0)+pay; remaining -= pay

        if remaining>0 and cc_data:
            t = cc_data[0][0]; allocs[t] = allocs.get(t,0)+remaining

        month_payoffs = []
        for n in list(sim):
            if sim[n]<=0: continue
            bal   = sim[n]
            dtype = data["debts"].get(n,{}).get("type","credit_card")
            apr   = data["debts"].get(n,{}).get("apr_monthly_pct",0.0)
            pay   = allocs.get(n,0)
            sim[n] = max(0, bal*(1+apr/100)-pay if dtype=="credit_card" else bal-pay)
            if sim[n]==0 and n not in payoffs:
                payoffs[n]=m; month_payoffs.append(n)

        rows.append({"month":m,"budget":budget,"total":sum(sim.values()),
                     "payoffs":month_payoffs,"allocs":allocs})
        m = month_add(m,1)

    return rows, payoffs

def get_ai_html(data):
    load_env()
    api_key = os.environ.get("OPENAI_API_KEY","")
    if not api_key: return None
    try:
        from openai import OpenAI
        latest  = latest_month(data)
        entries = data["months"][latest]
        cfg     = data.get("income_config",{})
        summary = []
        for name,e in entries.items():
            bal = e.get("balance",0) or 0
            if bal>0:
                summary.append({"name":name,"balance":bal,
                    "min_due":e.get("min_due",0) or 0,
                    "apr_monthly_pct":data["debts"].get(name,{}).get("apr_monthly_pct",0),
                    "type":data["debts"].get(name,{}).get("type","credit_card")})
        context = {"month":latest,"debts":summary,
            "monthly_budget_php":(cfg.get("monthly_sar",0)-cfg.get("expenses_sar",0))*cfg.get("sar_to_php",15),
            "total_debt":sum(d["balance"] for d in summary)}
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content":"Personal finance advisor for Filipino OFW. Be direct, specific, use numbers. Format in clean HTML using <p><ul><li><strong> tags only."},
                {"role":"user","content":f"Debt for {latest}:\n{json.dumps(context,indent=2)}\n\nGive: 1) Key observations (3 bullets) 2) Biggest risk 3) One action this month with exact peso amount 4) Projected savings following avalanche plan."}
            ], max_tokens=600)
        return resp.choices[0].message.content
    except Exception as e:
        return f"<p style='color:red'>AI error: {e}</p>"

# ── base layout ─────────────────────────────────────────────────────────────

BASE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Jayvee — Debt Tracker</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
nav{background:#1e293b;padding:14px 24px;display:flex;align-items:center;gap:8px;flex-wrap:wrap;border-bottom:1px solid #334155}
nav a{color:#94a3b8;text-decoration:none;padding:6px 14px;border-radius:8px;font-size:.85rem;transition:.15s}
nav a:hover,nav a.active{background:#334155;color:#e2e8f0}
nav .brand{font-weight:700;color:#e2e8f0;margin-right:12px;font-size:1rem}
.page{padding:28px 24px;max-width:1100px;margin:0 auto}
h2{font-size:1.3rem;font-weight:700;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:24px}
.card{background:#1e293b;border-radius:12px;padding:20px}
.card .label{color:#94a3b8;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}
.card .value{font-size:1.4rem;font-weight:700}
.red{color:#ef4444}.green{color:#22c55e}.yellow{color:#eab308}.blue{color:#3b82f6}
.section{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:20px}
.section h3{font-size:.8rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px}
.charts{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-bottom:20px}
.chart-card{background:#1e293b;border-radius:12px;padding:20px}
.chart-card h3{font-size:.8rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:14px}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:9px 12px;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8;border-bottom:1px solid #334155}
td{padding:9px 12px;font-size:.85rem;border-bottom:1px solid #0f172a}
tr:hover td{background:#273344}
.badge{padding:2px 8px;border-radius:999px;font-size:.72rem;font-weight:600}
.badge-green{background:#166534;color:#86efac}
.badge-red{background:#7f1d1d;color:#fca5a5}
.badge-yellow{background:#713f12;color:#fde68a}
.attack{background:#854d0e;color:#fde68a;padding:3px 10px;border-radius:999px;font-weight:700;font-size:.75rem}
form .row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
form .full{margin-bottom:12px}
label{display:block;font-size:.78rem;color:#94a3b8;margin-bottom:4px}
input,select{width:100%;padding:9px 12px;background:#0f172a;border:1px solid #334155;border-radius:8px;color:#e2e8f0;font-size:.9rem}
input:focus,select:focus{outline:none;border-color:#3b82f6}
.btn{padding:10px 22px;border-radius:8px;border:none;font-size:.9rem;font-weight:600;cursor:pointer;transition:.15s}
.btn-primary{background:#3b82f6;color:#fff}.btn-primary:hover{background:#2563eb}
.btn-success{background:#16a34a;color:#fff}.btn-success:hover{background:#15803d}
.btn-back{background:#334155;color:#e2e8f0;text-decoration:none;padding:10px 22px;border-radius:8px;font-size:.9rem;font-weight:600}
.alert{padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:.9rem}
.alert-success{background:#166534;color:#86efac}
.alert-error{background:#7f1d1d;color:#fca5a5}
.card-section{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:12px;border-left:3px solid #334155}
.card-section h4{font-size:.9rem;font-weight:600;margin-bottom:14px;color:#cbd5e1}
@media(max-width:768px){.charts{grid-template-columns:1fr}.row{grid-template-columns:1fr!important}}
</style>
</head>
<body>
<nav>
  <span class="brand">💳 Debt Tracker</span>
  <a href="/" class="{{ 'active' if active=='dashboard' else '' }}">Dashboard</a>
  <a href="/add" class="{{ 'active' if active=='add' else '' }}">Add Month</a>
  <a href="/remit" class="{{ 'active' if active=='remit' else '' }}">Remittance</a>
  <a href="/plan" class="{{ 'active' if active=='plan' else '' }}">Payoff Plan</a>
  <a href="/settings" class="{{ 'active' if active=='settings' else '' }}">Settings</a>
  <a href="/logout" style="margin-left:auto;color:#f87171">Logout</a>
</nav>
<div class="page">
"""

BASE_FOOT = """
</div>
</body>
</html>"""

# ── dashboard ────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    data    = load()
    latest  = latest_month(data)
    entries = data["months"].get(latest, {})
    cfg     = data.get("income_config", {})
    fixed_pmts = data.get("fixed_payments", {})

    sar_php    = cfg.get("sar_to_php", 15.0)
    phone_ends = cfg.get("phone", {}).get("ends", "2026-07")
    phone_sar  = cfg.get("phone", {}).get("monthly_sar", 0)
    base_sar   = cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0)
    budget_php = (base_sar - (phone_sar if latest <= phone_ends else 0)) * sar_php

    total_now = sum((e.get("balance",0) or 0) for e in entries.values())
    total_cc  = sum((e.get("balance",0) or 0) for n,e in entries.items()
                    if data["debts"].get(n,{}).get("type")=="credit_card")
    monthly_interest = sum((e.get("balance",0) or 0)*data["debts"].get(n,{}).get("apr_monthly_pct",0)/100
                           for n,e in entries.items()
                           if data["debts"].get(n,{}).get("type")=="credit_card")

    # history chart
    months_sorted = sorted(data["months"].keys())
    hist_labels = []; hist_totals = []
    for m in months_sorted:
        hist_labels.append(m)
        hist_totals.append(round(sum((e.get("balance",0) or 0) for e in data["months"][m].values()),2))

    # projection
    plan_rows, payoffs = compute_plan(data)
    proj_labels = [r["month"] for r in plan_rows]
    proj_totals = [round(r["total"],2) for r in plan_rows]
    debt_free   = plan_rows[-1]["month"] if plan_rows else "—"

    # donut
    palette = ["#ef4444","#f97316","#eab308","#22c55e","#3b82f6","#8b5cf6","#ec4899","#14b8a6","#f43f5e"]
    donut_labels=[]; donut_values=[]; donut_colors=[]
    for i,(n,e) in enumerate(entries.items()):
        bal = e.get("balance",0) or 0
        if bal>0:
            donut_labels.append(n.split("(")[0].strip())
            donut_values.append(round(bal,2))
            donut_colors.append(palette[i%len(palette)])

    # pay this month table
    remaining = budget_php; pay_alloc = {}
    for n,e in entries.items():
        bal = e.get("balance",0) or 0
        if bal<=0 or n not in fixed_pmts: continue
        fp_cfg=fixed_pmts[n]; threshold=fp_cfg.get("reduced_threshold",0)
        rate=fp_cfg.get("reduced_monthly",fp_cfg["monthly"]) if (threshold and bal<=threshold) else fp_cfg["monthly"]
        pay=min(rate,bal,remaining); pay_alloc[n]=pay; remaining-=pay

    cc_priority=[]
    for n,e in entries.items():
        bal=e.get("balance",0) or 0; mn=e.get("min_due",0) or 0
        dtype=data["debts"].get(n,{}).get("type","credit_card")
        apr=data["debts"].get(n,{}).get("apr_monthly_pct",0.0)
        if bal>0 and dtype=="credit_card":
            cc_priority.append((n,bal,mn,apr,bal*apr/100))
    cc_priority.sort(key=lambda x:-x[4])

    for n,bal,mn,apr,interest in cc_priority:
        pay=min(mn,bal,remaining); pay_alloc[n]=pay_alloc.get(n,0)+pay; remaining-=pay
    if remaining>0 and cc_priority:
        top=cc_priority[0][0]; pay_alloc[top]=pay_alloc.get(top,0)+remaining

    # status table rows
    status_rows = []
    for n,e in entries.items():
        bal=e.get("balance",0) or 0; mn=e.get("min_due",0) or 0
        dtype=data["debts"].get(n,{}).get("type","credit_card")
        apr=data["debts"].get(n,{}).get("apr_monthly_pct",0.0)
        paid=e.get("paid_on",""); due=e.get("due_date","—")
        interest=bal*apr/100 if dtype=="credit_card" else 0
        status_rows.append({"name":n,"balance":bal,"min_due":mn,"interest":interest,
                             "due":due,"paid":paid,"done":bal==0 and not mn})

    tmpl = BASE + """

<h2>Dashboard — {{ latest }}</h2>

<div class="grid">
  <div class="card"><div class="label">Total Debt</div><div class="value red">{{ total_now }}</div></div>
  <div class="card"><div class="label">Credit Cards</div><div class="value yellow">{{ total_cc }}</div></div>
  <div class="card"><div class="label">Interest / Month</div><div class="value red">{{ monthly_interest }}</div></div>
  <div class="card"><div class="label">Debt-Free Target</div><div class="value green">{{ debt_free }}</div></div>
  <div class="card"><div class="label">Monthly Budget</div><div class="value blue">{{ budget_php }}</div></div>
  <div class="card"><div class="label">SAR→PHP Rate</div><div class="value">1 SAR = ₱{{ rate }}</div></div>
</div>

<div class="charts">
  <div class="chart-card"><h3>Balance Trend + Projection</h3><canvas id="trendChart" height="110"></canvas></div>
  <div class="chart-card"><h3>Current Breakdown</h3><canvas id="donutChart"></canvas></div>
</div>

<div class="section" style="border:2px solid #854d0e">
  <h3 style="color:#fde68a">💰 Pay This Month — Budget {{ budget_php }}</h3>
  <p style="color:#94a3b8;font-size:.8rem;margin-bottom:14px">Avalanche: minimums on all, everything extra → ATTACK card first.</p>
  <table>
    <thead><tr><th>#</th><th>Card / Loan</th><th>Balance</th><th>Min Due</th><th>Interest/mo</th><th>Extra</th><th>→ PAY THIS MONTH</th></tr></thead>
    <tbody>
      {% for n,e in entries.items() %}
        {% if n in fixed_pmts and (e.balance or 0) > 0 %}
        <tr>
          <td><span style="color:#94a3b8">Fixed</span></td>
          <td>{{ n }}</td>
          <td>₱{{ "{:,.2f}".format(e.balance or 0) }}</td>
          <td>₱{{ "{:,.2f}".format(e.min_due or 0) }}</td>
          <td>—</td><td>—</td>
          <td><strong style="color:#22c55e">₱{{ "{:,.2f}".format(pay_alloc.get(n,0)) }}</strong></td>
        </tr>
        {% endif %}
      {% endfor %}
      {% for rank,(n,bal,mn,apr,interest) in enumerate(cc_priority, 1) %}
      <tr>
        <td>{% if rank==1 %}<span class="attack">ATTACK</span>{% else %}#{{ rank }}{% endif %}</td>
        <td>{{ n }}</td>
        <td>₱{{ "{:,.2f}".format(bal) }}</td>
        <td>₱{{ "{:,.2f}".format(mn) }}</td>
        <td style="color:#ef4444">₱{{ "{:,.2f}".format(interest) }}</td>
        <td>{% set extra=pay_alloc.get(n,0)-mn %}{% if extra>0.5 %}<span style="color:#22c55e">+₱{{ "{:,.2f}".format(extra) }}</span>{% else %}—{% endif %}</td>
        <td><strong style="color:#22c55e">₱{{ "{:,.2f}".format(pay_alloc.get(n,0)) }}</strong></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<div class="section">
  <h3>All Cards — Status {{ latest }}</h3>
  <table>
    <thead><tr><th>Card / Loan</th><th>Balance</th><th>Min Due</th><th>Interest/mo</th><th>Due Date</th><th>Status</th></tr></thead>
    <tbody>
      {% for r in status_rows %}
      <tr>
        <td>{{ r.name }}</td>
        {% if r.done %}<td colspan="5" style="color:#22c55e;font-weight:600">DONE ✓</td>
        {% else %}
        <td>₱{{ "{:,.2f}".format(r.balance) }}</td>
        <td>₱{{ "{:,.2f}".format(r.min_due) }}</td>
        <td style="color:#ef4444">{% if r.interest > 0 %}₱{{ "{:,.2f}".format(r.interest) }}{% else %}—{% endif %}</td>
        <td>{{ r.due }}</td>
        <td>{% if r.paid and r.paid not in ('Good','Ready') %}<span class="badge badge-green">✓ {{ r.paid }}</span>
            {% elif r.paid %}<span class="badge badge-yellow">{{ r.paid }}</span>
            {% else %}<span class="badge badge-red">Unpaid</span>{% endif %}</td>
        {% endif %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

{% if ai_html %}
<div class="section" style="border:2px solid #1d4ed8">
  <h3 style="color:#93c5fd">🤖 AI Analysis — GPT-4o-mini</h3>
  <div style="font-size:.9rem;line-height:1.7">{{ ai_html|safe }}</div>
  <p style="color:#475569;font-size:.75rem;margin-top:10px">Generated {{ today }} · Based on {{ latest }} balances</p>
</div>
{% else %}
<div class="section" style="border:1px solid #334155">
  <h3>🤖 AI Analysis</h3>
  <p style="color:#94a3b8;font-size:.85rem">No OpenAI key set. <a href="/settings" style="color:#3b82f6">Add key in Settings →</a></p>
</div>
{% endif %}

<script>
const hL={{ hist_labels|tojson }}, hT={{ hist_totals|tojson }};
const pL={{ proj_labels|tojson }}, pT={{ proj_totals|tojson }};
const allL=[...hL,...pL];
const hD=[...hT,...new Array(pL.length).fill(null)];
const pD=[...new Array(hL.length-1).fill(null),hT[hT.length-1],...pT];
new Chart(document.getElementById('trendChart'),{type:'line',data:{labels:allL,datasets:[
  {label:'Actual',data:hD,borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,.1)',tension:.3,fill:true,pointRadius:4},
  {label:'Projected',data:pD,borderColor:'#22c55e',backgroundColor:'rgba(34,197,94,.05)',borderDash:[5,5],tension:.3,fill:true,pointRadius:2}
]},options:{responsive:true,plugins:{legend:{labels:{color:'#94a3b8'}}},scales:{x:{ticks:{color:'#64748b',maxTicksLimit:12},grid:{color:'#1e293b'}},y:{ticks:{color:'#64748b',callback:v=>'₱'+v.toLocaleString()},grid:{color:'#334155'}}}}});
new Chart(document.getElementById('donutChart'),{type:'doughnut',data:{labels:{{ donut_labels|tojson }},datasets:[{data:{{ donut_values|tojson }},backgroundColor:{{ donut_colors|tojson }},borderWidth:2,borderColor:'#1e293b'}]},options:{responsive:true,plugins:{legend:{position:'bottom',labels:{color:'#94a3b8',font:{size:11},padding:8}}}}}});
</script>
""" + BASE_FOOT

    ai_html = get_ai_html(data)

    return render_template_string(tmpl,
        active="dashboard", latest=latest, entries=entries,
        fixed_pmts=fixed_pmts, pay_alloc=pay_alloc, cc_priority=cc_priority,
        status_rows=status_rows, enumerate=enumerate,
        total_now=fp(total_now), total_cc=fp(total_cc),
        monthly_interest=fp(monthly_interest), debt_free=debt_free,
        budget_php=fp(budget_php), rate=sar_php,
        hist_labels=hist_labels, hist_totals=hist_totals,
        proj_labels=proj_labels, proj_totals=proj_totals,
        donut_labels=donut_labels, donut_values=donut_values, donut_colors=donut_colors,
        ai_html=ai_html, today=date.today())

# ── add month ────────────────────────────────────────────────────────────────

@app.route("/add", methods=["GET","POST"])
@login_required
def add_month():
    data = load()
    debt_names = list(data["debts"].keys())
    msg = None

    if request.method == "POST":
        month = request.form.get("month","").strip()
        if month:
            entries = {}
            for n in debt_names:
                prefix = f"d_{debt_names.index(n)}_"
                bal_s = request.form.get(prefix+"balance","").replace(",","")
                mn_s  = request.form.get(prefix+"min_due","").replace(",","")
                pmt_s = request.form.get(prefix+"payment","").replace(",","")
                due   = request.form.get(prefix+"due_date","").strip()
                paid  = request.form.get(prefix+"paid_on","").strip()
                note  = request.form.get(prefix+"note","").strip()
                if not bal_s: continue
                try:
                    entry = {"balance":float(bal_s),"min_due":float(mn_s) if mn_s else 0,
                             "payment":float(pmt_s) if pmt_s else 0}
                    if due:  entry["due_date"]=due
                    if paid: entry["paid_on"]=paid
                    if note: entry["note"]=note
                    entries[n] = entry
                except ValueError:
                    continue
            data["months"][month] = entries
            save(data)
            return redirect(url_for("dashboard") + f"?msg=Saved+{month}")

    tmpl = BASE + """

<h2>Add / Update Month</h2>
{% if msg %}<div class="alert alert-success">{{ msg }}</div>{% endif %}
<form method="POST">
  <div class="section">
    <h3>Month</h3>
    <div style="max-width:200px">
      <label>Month (YYYY-MM)</label>
      <input name="month" placeholder="2026-05" required pattern="\\d{4}-\\d{2}">
    </div>
  </div>

  {% for i, name in enumerate(debt_names) %}
  <div class="card-section">
    <h4>{{ name }}</h4>
    <div class="row">
      <div><label>Balance (Total Amount Due)</label><input name="d_{{ i }}_balance" placeholder="0.00"></div>
      <div><label>Minimum Due</label><input name="d_{{ i }}_min_due" placeholder="0.00"></div>
    </div>
    <div class="row">
      <div><label>Payment Made</label><input name="d_{{ i }}_payment" placeholder="0.00"></div>
      <div><label>Due Date (e.g. Jun 12)</label><input name="d_{{ i }}_due_date" placeholder="Jun 12"></div>
    </div>
    <div class="row">
      <div><label>Paid On (e.g. 2026-05-25)</label><input name="d_{{ i }}_paid_on" placeholder="leave blank if unpaid"></div>
      <div><label>Note (optional)</label><input name="d_{{ i }}_note" placeholder="e.g. 16/36"></div>
    </div>
  </div>
  {% endfor %}

  <div style="display:flex;gap:12px;margin-top:8px">
    <button type="submit" class="btn btn-success">💾 Save Month</button>
    <a href="/" class="btn-back">← Back</a>
  </div>
</form>
""" + BASE_FOOT

    return render_template_string(tmpl, active="add", debt_names=debt_names,
                                  enumerate=enumerate, msg=request.args.get("msg"))

# ── remittance ───────────────────────────────────────────────────────────────

@app.route("/remit", methods=["GET","POST"])
@login_required
def remit():
    data   = load()
    cfg    = data.get("income_config",{})
    rate   = cfg.get("sar_to_php",15.0)
    result = None

    if request.method == "POST":
        try:
            sar = float(request.form.get("sar","0").replace(",",""))
            php = sar * rate
            fixed_pmts = data.get("fixed_payments",{})
            latest  = latest_month(data)
            entries = data["months"].get(latest,{})
            remaining = php; pay_alloc = {}

            for n,e in entries.items():
                bal=e.get("balance",0) or 0
                if bal<=0 or n not in fixed_pmts: continue
                fp_cfg=fixed_pmts[n]; threshold=fp_cfg.get("reduced_threshold",0)
                rate2=fp_cfg.get("reduced_monthly",fp_cfg["monthly"]) if (threshold and bal<=threshold) else fp_cfg["monthly"]
                pay=min(rate2,bal,remaining); pay_alloc[n]=pay; remaining-=pay

            cc_p=[]
            for n,e in entries.items():
                bal=e.get("balance",0) or 0; mn=e.get("min_due",0) or 0
                dtype=data["debts"].get(n,{}).get("type","credit_card")
                apr=data["debts"].get(n,{}).get("apr_monthly_pct",0.0)
                if bal>0 and dtype=="credit_card":
                    cc_p.append((n,bal,mn,apr,bal*apr/100))
            cc_p.sort(key=lambda x:-x[4])
            for n,bal,mn,apr,_ in cc_p:
                pay=min(mn,bal,remaining); pay_alloc[n]=pay_alloc.get(n,0)+pay; remaining-=pay
            if remaining>0 and cc_p:
                t=cc_p[0][0]; pay_alloc[t]=pay_alloc.get(t,0)+remaining

            standard=(cfg.get("monthly_sar",0)-cfg.get("expenses_sar",0))*rate
            result={"sar":sar,"php":php,"standard":standard,"pay_alloc":pay_alloc,
                    "entries":entries,"cc_p":cc_p,"fixed_pmts":fixed_pmts}
        except ValueError:
            pass

    tmpl = BASE + """

<h2>Remittance Planner</h2>
<div class="section">
  <h3>How much are you sending this month?</h3>
  <form method="POST" style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
    <div>
      <label>SAR Amount</label>
      <input name="sar" placeholder="5650" style="max-width:160px" value="{{ request.form.get('sar','') }}">
    </div>
    <div>
      <label>Current Rate</label>
      <input value="1 SAR = ₱{{ rate }}" disabled style="max-width:160px;color:#94a3b8">
    </div>
    <button type="submit" class="btn btn-primary">Calculate →</button>
    <a href="/settings" style="color:#3b82f6;font-size:.85rem;align-self:center">Change rate</a>
  </form>
</div>

{% if result %}
<div class="section" style="border:2px solid {% if result.php >= result.standard %}#166534{% else %}#7f1d1d{% endif %}">
  <h3>Allocation Plan</h3>
  <div style="display:flex;gap:24px;margin-bottom:16px;flex-wrap:wrap">
    <div><span style="color:#94a3b8;font-size:.8rem">Sending</span><div style="font-size:1.3rem;font-weight:700">{{ "{:,.0f}".format(result.sar) }} SAR</div></div>
    <div><span style="color:#94a3b8;font-size:.8rem">PHP Received</span><div class="green" style="font-size:1.3rem;font-weight:700">₱{{ "{:,.2f}".format(result.php) }}</div></div>
    {% if result.php >= result.standard %}
    <div><span style="color:#94a3b8;font-size:.8rem">Extra vs Plan</span><div class="green" style="font-size:1.3rem;font-weight:700">+₱{{ "{:,.2f}".format(result.php - result.standard) }}</div></div>
    {% else %}
    <div><span style="color:#94a3b8;font-size:.8rem">Short vs Plan</span><div class="red" style="font-size:1.3rem;font-weight:700">-₱{{ "{:,.2f}".format(result.standard - result.php) }}</div></div>
    {% endif %}
  </div>
  <table>
    <thead><tr><th>Card / Loan</th><th>Balance</th><th>Min Due</th><th>→ PAY</th><th>Note</th></tr></thead>
    <tbody>
      {% for n,e in result.entries.items() %}
        {% if n in result.fixed_pmts and (e.get('balance') or 0) > 0 %}
        <tr>
          <td>{{ n }}</td>
          <td>₱{{ "{:,.2f}".format(e.get('balance') or 0) }}</td>
          <td>₱{{ "{:,.2f}".format(e.get('min_due') or 0) }}</td>
          <td><strong style="color:#22c55e">₱{{ "{:,.2f}".format(result.pay_alloc.get(n,0)) }}</strong></td>
          <td style="color:#94a3b8">Fixed</td>
        </tr>
        {% endif %}
      {% endfor %}
      {% for n,bal,mn,apr,interest in result.cc_p %}
      {% set alloc=result.pay_alloc.get(n,0) %}
      {% set extra=alloc-mn %}
      <tr>
        <td>{{ n }}{% if loop.first %} <span class="attack">ATTACK</span>{% endif %}</td>
        <td>₱{{ "{:,.2f}".format(bal) }}</td>
        <td>₱{{ "{:,.2f}".format(mn) }}</td>
        <td><strong style="color:#22c55e">₱{{ "{:,.2f}".format(alloc) }}</strong></td>
        <td>{% if extra>0.5 %}<span style="color:#22c55e">+₱{{ "{:,.2f}".format(extra) }} extra</span>{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}
""" + BASE_FOOT

    return render_template_string(tmpl, active="remit", rate=rate, result=result, request=request)

# ── payoff plan ───────────────────────────────────────────────────────────────

@app.route("/plan")
@login_required
def plan():
    data     = load()
    strategy = request.args.get("strategy","avalanche")
    rows, payoffs = compute_plan(data, strategy)

    tmpl = BASE + """

<h2>Payoff Plan</h2>
<div style="display:flex;gap:10px;margin-bottom:20px">
  <a href="/plan?strategy=avalanche" class="btn {% if strategy=='avalanche' %}btn-primary{% else %}btn-back{% endif %}">Avalanche</a>
  <a href="/plan?strategy=snowball"  class="btn {% if strategy=='snowball'  %}btn-primary{% else %}btn-back{% endif %}">Snowball</a>
</div>

<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr))">
  {% for name,when in payoffs.items() %}
  <div class="card">
    <div class="label">{{ name.split('(')[0].strip() }}</div>
    <div class="value green" style="font-size:1.1rem">{{ when }}</div>
  </div>
  {% endfor %}
</div>

<div class="section">
  <h3>Month-by-Month</h3>
  <table>
    <thead><tr><th>Month</th><th>Budget</th><th>Total Debt</th><th>Paid Off</th></tr></thead>
    <tbody>
      {% for r in rows %}
      <tr>
        <td>{{ r.month }}</td>
        <td>₱{{ "{:,.0f}".format(r.budget) }}</td>
        <td style="color:{% if r.total < 200000 %}#22c55e{% elif r.total < 500000 %}#eab308{% else %}#ef4444{% endif %}">
          ₱{{ "{:,.2f}".format(r.total) }}</td>
        <td style="color:#22c55e">{{ r.payoffs|join(', ') }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
""" + BASE_FOOT

    return render_template_string(tmpl, active="plan", rows=rows, payoffs=payoffs, strategy=strategy)

# ── settings ─────────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET","POST"])
@login_required
def settings():
    data = load()
    cfg  = data.get("income_config",{})
    msg  = None

    if request.method == "POST":
        action = request.form.get("action")
        if action == "rate":
            try:
                new_rate = float(request.form.get("rate","0"))
                data["income_config"]["sar_to_php"] = new_rate
                save(data); msg = f"Rate updated → 1 SAR = ₱{new_rate}"
            except ValueError:
                msg = "Invalid rate."
        elif action == "apikey":
            key = request.form.get("apikey","").strip()
            if key:
                ENV_FILE.write_text(f"OPENAI_API_KEY={key}\n")
                msg = "API key saved."

    tmpl = BASE + """

<h2>Settings</h2>
{% if msg %}<div class="alert alert-success">{{ msg }}</div>{% endif %}

<div class="section">
  <h3>SAR → PHP Rate</h3>
  <p style="color:#94a3b8;font-size:.85rem;margin-bottom:14px">Check Wise or Western Union for current rate before updating.</p>
  <form method="POST" style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
    <input type="hidden" name="action" value="rate">
    <div>
      <label>Current: 1 SAR = ₱{{ cfg.get('sar_to_php', 15.0) }}</label>
      <input name="rate" placeholder="{{ cfg.get('sar_to_php', 15.0) }}" style="max-width:160px">
    </div>
    <button type="submit" class="btn btn-primary">Update Rate</button>
  </form>
</div>

<div class="section">
  <h3>OpenAI API Key</h3>
  <p style="color:#94a3b8;font-size:.85rem;margin-bottom:14px">Required for AI analysis. Key is stored locally in .env file.</p>
  <form method="POST" style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
    <input type="hidden" name="action" value="apikey">
    <div style="flex:1;min-width:300px">
      <label>API Key (sk-...)</label>
      <input name="apikey" type="password" placeholder="sk-...">
    </div>
    <button type="submit" class="btn btn-primary">Save Key</button>
  </form>
</div>

<div class="section">
  <h3>Income Config</h3>
  <table style="max-width:400px">
    <tr><td style="color:#94a3b8">Monthly Salary</td><td>{{ cfg.get('monthly_sar',0) }} SAR</td></tr>
    <tr><td style="color:#94a3b8">Saudi Expenses</td><td>{{ cfg.get('expenses_sar',0) }} SAR</td></tr>
    <tr><td style="color:#94a3b8">Phone (ends {{ cfg.get('phone',{}).get('ends','—') }})</td><td>{{ cfg.get('phone',{}).get('monthly_sar',0) }} SAR</td></tr>
    <tr><td style="color:#94a3b8">Net Remittable</td><td><strong>{{ cfg.get('monthly_sar',0) - cfg.get('expenses_sar',0) }} SAR</strong></td></tr>
  </table>
</div>
""" + BASE_FOOT

    return render_template_string(tmpl, active="settings", cfg=cfg, msg=msg)

# ── run ───────────────────────────────────────────────────────────────────────

def open_browser():
    webbrowser.open("http://localhost:5050")

if __name__ == "__main__":
    threading.Timer(1.0, open_browser).start()
    print("\n  Debt Tracker running → http://localhost:5050")
    print("  Press Ctrl+C to stop\n")
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5050)), debug=debug, use_reloader=False)
