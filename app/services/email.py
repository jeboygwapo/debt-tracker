import logging
import os

import httpx

logger = logging.getLogger("app.email")

RESEND_API_URL = "https://api.resend.com/emails"
FROM_ADDRESS = os.getenv("RESEND_FROM", "Debt Tracker <noreply@personal-debt-tracker.fly.dev>")


class EmailError(Exception):
    pass


async def send_verification_email(to_email: str, username: str, token: str, base_url: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise EmailError("RESEND_API_KEY not configured")

    verify_url = f"{base_url}/verify/{token}"

    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px">
      <h2 style="margin-bottom:8px;color:#1e293b">Verify your email</h2>
      <p style="color:#64748b;margin-bottom:24px">Hi {username}, confirm your email address to secure your account.</p>
      <a href="{verify_url}"
         style="display:inline-block;padding:12px 24px;background:#6366f1;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">
        Verify Email
      </a>
      <p style="color:#94a3b8;font-size:.8rem;margin-top:24px">Link expires in 24 hours. If you didn't sign up, ignore this email.</p>
      <p style="color:#94a3b8;font-size:.75rem;margin-top:8px">Or copy this link: {verify_url}</p>
    </div>
    """

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"from": FROM_ADDRESS, "to": [to_email], "subject": "Verify your Debt Tracker email", "html": html},
            )
        except httpx.HTTPError as e:
            logger.error("Resend verify request failed: %s (from=%s to=%s)", e, FROM_ADDRESS, to_email)
            raise EmailError(f"Resend request failed: {e}") from e
        if resp.status_code not in (200, 201):
            logger.error("Resend verify %s: %s (from=%s to=%s)", resp.status_code, resp.text, FROM_ADDRESS, to_email)
            raise EmailError(f"Resend API error {resp.status_code}: {resp.text}")


async def send_password_reset_email(to_email: str, username: str, token: str, base_url: str) -> None:
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        raise EmailError("RESEND_API_KEY not configured")

    reset_url = f"{base_url}/reset-password/{token}"

    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px">
      <h2 style="margin-bottom:8px;color:#1e293b">Reset your password</h2>
      <p style="color:#64748b;margin-bottom:24px">Hi {username}, click below to set a new password for your Debt Tracker account.</p>
      <a href="{reset_url}"
         style="display:inline-block;padding:12px 24px;background:#6366f1;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">
        Reset Password
      </a>
      <p style="color:#94a3b8;font-size:.8rem;margin-top:24px">Link expires in 1 hour. If you didn't request this, ignore this email.</p>
      <p style="color:#94a3b8;font-size:.75rem;margin-top:8px">Or copy this link: {reset_url}</p>
    </div>
    """

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"from": FROM_ADDRESS, "to": [to_email], "subject": "Reset your Debt Tracker password", "html": html},
            )
        except httpx.HTTPError as e:
            logger.error("Resend reset request failed: %s (from=%s to=%s)", e, FROM_ADDRESS, to_email)
            raise EmailError(f"Resend request failed: {e}") from e
        if resp.status_code not in (200, 201):
            logger.error("Resend reset %s: %s (from=%s to=%s)", resp.status_code, resp.text, FROM_ADDRESS, to_email)
            raise EmailError(f"Resend API error {resp.status_code}: {resp.text}")
