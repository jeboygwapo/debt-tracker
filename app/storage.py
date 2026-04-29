import json
from typing import Any, Dict

from .config import settings


def load() -> Dict[str, Any]:
    with open(settings.data_file) as f:
        return json.load(f)


def save(data: Dict[str, Any]) -> None:
    with open(settings.data_file, "w") as f:
        json.dump(data, f, indent=2)
