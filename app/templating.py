import json
from pathlib import Path

from fastapi.templating import Jinja2Templates
from markupsafe import Markup

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["tojson"] = lambda v: Markup(json.dumps(v))
templates.env.filters["peso"] = lambda v: f"₱{v:,.2f}"
