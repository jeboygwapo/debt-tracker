from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import hash_password, settings
from ..templating import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
async def login_post(request: Request):
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))

    if username == settings.app_user and hash_password(password) == settings.app_password_hash:
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=303)

    return templates.TemplateResponse(
        request, "login.html", {"error": "Invalid username or password."}, status_code=401
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
