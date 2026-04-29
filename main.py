#!/usr/bin/env python3
import threading
import webbrowser
from pathlib import Path

import uvicorn

from app.config import load_env_file, settings

load_env_file(Path(__file__).parent / ".env")
load_env_file(settings.env_file)

from app.config import _migrate_plaintext_password
_migrate_plaintext_password(settings.env_file)

from app import create_app

app = create_app()


if __name__ == "__main__":
    def _open_browser():
        webbrowser.open(f"http://localhost:{settings.port}")

    threading.Timer(1.5, _open_browser).start()
    print(f"\n  Debt Tracker → http://localhost:{settings.port}")
    print(f"  Docs         → http://localhost:{settings.port}/docs")
    print("  Press Ctrl+C to stop\n")
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=False)
