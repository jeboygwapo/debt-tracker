import json
from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from .csrf import get_csrf_token

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["tojson"] = lambda v: Markup(json.dumps(v))

@jinja2.pass_context
def _currency_filter(ctx, v):
    request = ctx.get("request")
    symbol = request.session.get("currency_symbol", "₱") if request else "₱"
    return f"{symbol}{v:,.2f}"

def _currency_symbol(request) -> str:
    return request.session.get("currency_symbol", "₱")

def _income_currency(request) -> str:
    return request.session.get("income_currency", "SAR")

templates.env.filters["peso"] = _currency_filter
templates.env.globals["csrf_token"] = get_csrf_token
templates.env.globals["currency_symbol"] = _currency_symbol
templates.env.globals["income_currency"] = _income_currency
