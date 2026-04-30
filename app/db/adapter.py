"""Converts DB records into the dict format the planner/AI services expect."""
from .models import AiCache, Debt, MonthlyEntry, User


def build_debts_dict(debts: list[Debt]) -> dict:
    return {
        d.name: {
            "type": d.type,
            "apr_monthly_pct": d.apr_monthly_pct,
            "note": d.note or "",
        }
        for d in debts
    }


def build_fixed_payments(debts: list[Debt]) -> dict:
    out = {}
    for d in debts:
        if d.is_fixed and d.fixed_monthly:
            entry = {"monthly": d.fixed_monthly, "ends": d.fixed_ends or ""}
            if d.fixed_reduced_monthly:
                entry["reduced_monthly"] = d.fixed_reduced_monthly
            if d.fixed_reduced_threshold:
                entry["reduced_threshold"] = d.fixed_reduced_threshold
            out[d.name] = entry
    return out


def build_months_dict(entries: list[MonthlyEntry], debts: list[Debt]) -> dict:
    debt_by_id = {d.id: d.name for d in debts}
    months: dict[str, dict] = {}
    for e in entries:
        name = debt_by_id.get(e.debt_id)
        if not name:
            continue
        months.setdefault(e.month, {})[name] = {
            "balance": e.balance,
            "min_due": e.min_due,
            "payment": e.payment,
            "paid_on": e.paid_on or "",
            "due_date": e.due_date or "",
            "note": e.note or "",
        }
    return months


def build_data_dict(
    user: User,
    debts: list[Debt],
    entries: list[MonthlyEntry],
    ai_cache: AiCache | None = None,
) -> dict:
    cache = {}
    if ai_cache:
        cache = {
            "data_hash": ai_cache.data_hash,
            "html": ai_cache.html,
            "generated_at": str(ai_cache.generated_at),
        }
    return {
        "income_config": user.income_config or {},
        "debts": build_debts_dict(debts),
        "fixed_payments": build_fixed_payments(debts),
        "months": build_months_dict(entries, debts),
        "ai_cache": cache,
    }


def debt_name_to_id(debts: list[Debt]) -> dict[str, int]:
    return {d.name: d.id for d in debts}
