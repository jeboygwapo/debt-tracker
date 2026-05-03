"""E2E — full login → dashboard → logout cycle.

Critical user path. If this breaks, no other E2E test can run, so it is
sentinel-positioned alphabetically.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_login_success_lands_user(page, base_url, admin_credentials):
    page.goto(f"{base_url}/login")
    assert page.title().startswith("Debt Tracker")
    page.fill('input[name="username"]', admin_credentials["username"])
    page.fill('input[name="password"]', admin_credentials["password"])
    page.click('button[type="submit"]')

    page.wait_for_load_state("networkidle")
    # New user with no debts is redirected to /debts; otherwise dashboard.
    assert page.url.rstrip("/") in (base_url, f"{base_url}/debts")


def test_login_invalid_shows_error(page, base_url):
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', "no-such-user")
    page.fill('input[name="password"]', "WrongPassword123!")
    page.click('button[type="submit"]')

    page.wait_for_load_state("networkidle")
    body = page.content().lower()
    assert "invalid" in body or "remaining" in body


def test_logout_clears_session(logged_in_page, base_url):
    logged_in_page.goto(f"{base_url}/logout")
    logged_in_page.wait_for_load_state("networkidle")
    # Logout sends us back to /login (303 → followed)
    assert logged_in_page.url.rstrip("/").endswith("/login")

    # Hitting / now should redirect to /welcome (anonymous user)
    logged_in_page.goto(f"{base_url}/")
    logged_in_page.wait_for_load_state("networkidle")
    assert logged_in_page.url.rstrip("/").endswith("/welcome")
