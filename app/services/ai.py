import hashlib
import json
from datetime import date
from typing import Optional

from ..config import settings, load_env_file
from ..storage import save
from .planner import latest_month


def _compute_hash(data: dict) -> str:
    latest = latest_month(data)
    entries = data["months"].get(latest, {})
    blob = json.dumps({"month": latest, "entries": entries}, sort_keys=True)
    return hashlib.md5(blob.encode()).hexdigest()


def get_analysis(data: dict, force: bool = False) -> Optional[str]:
    load_env_file(settings.env_file)
    api_key = settings.openai_api_key
    if not api_key:
        return None

    current_hash = _compute_hash(data)
    cache = data.get("ai_cache", {})
    if not force and cache.get("data_hash") == current_hash and cache.get("html"):
        return cache["html"]

    try:
        from openai import OpenAI

        latest = latest_month(data)
        entries = data["months"][latest]
        cfg = data.get("income_config", {})

        summary = [
            {
                "name": name,
                "balance": e.get("balance", 0) or 0,
                "min_due": e.get("min_due", 0) or 0,
                "payment_made": e.get("payment", 0) or 0,
                "paid_on": e.get("paid_on", "") or "",
                "apr_monthly_pct": data["debts"].get(name, {}).get("apr_monthly_pct", 0),
                "type": data["debts"].get(name, {}).get("type", "credit_card"),
            }
            for name, e in entries.items()
            if (e.get("balance", 0) or 0) > 0
        ]

        context = {
            "month": latest,
            "debts": summary,
            "monthly_budget_php": (
                (cfg.get("monthly_sar", 0) - cfg.get("expenses_sar", 0))
                * cfg.get("sar_to_php", 15)
            ),
            "total_debt": sum(d["balance"] for d in summary),
            "total_paid": sum(d["payment_made"] for d in summary),
        }

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Personal finance advisor for Filipino OFW. Be direct, specific, "
                        "use numbers. Format in clean HTML using <p><ul><li><strong> tags only."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Debt for {latest}:\n{json.dumps(context, indent=2)}\n\n"
                        "Give: 1) Key observations (3 bullets) including which debts were paid and if payment_made covers min_due "
                        "2) Biggest risk 3) One action this month with exact peso amount "
                        "4) Any unpaid or underpaid debts that need attention "
                        "5) Projected savings following avalanche plan."
                    ),
                },
            ],
            max_tokens=600,
        )
        html = resp.choices[0].message.content
        data["ai_cache"] = {
            "data_hash": current_hash,
            "html": html,
            "generated_at": str(date.today()),
        }
        save(data)
        return html
    except Exception as e:
        return f"<p style='color:red'>AI error: {e}</p>"
