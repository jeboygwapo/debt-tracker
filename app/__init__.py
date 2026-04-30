from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .routes import admin as admin_routes, auth, pages, api as api_routes, debts as debts_routes


def create_app() -> FastAPI:
    app = FastAPI(title="Debt Tracker", docs_url="/docs")
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

    static_dir = Path(__file__).parent.parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth.router)
    app.include_router(pages.router)
    app.include_router(api_routes.router)
    app.include_router(debts_routes.router)
    app.include_router(admin_routes.router)

    return app
