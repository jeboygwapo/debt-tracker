import hashlib
import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import load_env_file, settings
from .planner import latest_month


def compute_hash(data: dict) -> str:
    latest = latest_month(data)
    entries = data["months"].get(latest, {})
    blob = json.dumps({"month": latest, "entries": entries}, sort_keys=True)
    return hashlib.md5(blob.encode()).hexdigest()


async def get_analysis(
    data: dict,
    db: AsyncSession,
    user_id: int,
    force: bool = False,
) -> Optional[str]:
    from ..db.crud import get_ai_cache, set_ai_cache

    load_env_file(settings.env_file)
    api_key = settings.openai_api_key
    if not api_key:
        return None

    current_hash = compute_hash(data)
    if not force:
        cache = await get_ai_cache(db, user_id)
        if cache and cache.data_hash == current_hash and cache.html:
            return cache.html

    try:
        from openai import OpenAI

        latest = latest_month(data)
        entries = data["months"].get(latest, {})
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
                        "Give: 1) Key observations (3 bullets) including which debts were paid "
                        "and if payment_made covers min_due "
                        "2) Biggest risk 3) One action this month with exact peso amount "
                        "4) Any unpaid or underpaid debts that need attention "
                        "5) Projected savings following avalanche plan."
                    ),
                },
            ],
            max_tokens=600,
        )
        html = resp.choices[0].message.content
        await set_ai_cache(db, user_id, current_hash, html)
        return html

    except Exception as e:
        return f"<p style='color:red'>AI error: {e}</p>"
