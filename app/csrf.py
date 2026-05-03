import secrets

from fastapi import HTTPException, Request

CSRF_SESSION_KEY = "csrf_token"


def get_csrf_token(request: Request) -> str:
    token = request.session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_hex(32)
        request.session[CSRF_SESSION_KEY] = token
    return token


async def validate_csrf(request: Request) -> None:
    expected = request.session.get(CSRF_SESSION_KEY, "")
    form = await request.form()
    token = str(form.get(CSRF_SESSION_KEY, ""))
    if not expected or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
