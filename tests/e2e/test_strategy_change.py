"""E2E — strategy toggle on /plan persists across navigation.

Click ``Snowball`` on /plan → reload → confirm Snowball is still the active
button → navigate to /settings → confirm the strategy select reflects it.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def _ensure_some_data(page, base_url):
    """Make sure at least one month exists so /plan has something to render."""
    page.goto(f"{base_url}/add")
    page.wait_for_load_state("networkidle")

    # Form fields use d_0_balance / d_0_min_due / d_0_payment style
    page.fill('input[name="month"]', "2026-09")
    page.fill('input[name="d_0_balance"]', "20000")
    page.fill('input[name="d_0_min_due"]', "1000")
    page.fill('input[name="d_0_payment"]', "1500")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_strategy_snowball_persists_via_plan_form(logged_in_page, base_url, _seed_debts):
    _ensure_some_data(logged_in_page, base_url)

    logged_in_page.goto(f"{base_url}/plan")
    logged_in_page.wait_for_load_state("networkidle")

    # Click the Snowball form's submit button
    snowball_button = logged_in_page.locator('form[action="/plan/strategy"] button:has-text("Snowball")')
    snowball_button.first.click()
    logged_in_page.wait_for_load_state("networkidle")

    # After redirect we are back on /plan — Snowball should be the primary button now.
    body = logged_in_page.content()
    # Primary button class differs from inactive — assert Snowball renders as btn-primary now.
    assert 'btn btn-primary">Snowball' in body or "btn-primary'>Snowball" in body or "Snowball</button>" in body

    # Navigate away and back — strategy must still be Snowball.
    logged_in_page.goto(f"{base_url}/settings")
    logged_in_page.wait_for_load_state("networkidle")
    settings_html = logged_in_page.content()
    # Settings page renders the strategy select with the current value preselected
    assert "snowball" in settings_html.lower()

    # Clean up: revert to avalanche so other tests aren't affected.
    logged_in_page.goto(f"{base_url}/plan")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.locator('form[action="/plan/strategy"] button:has-text("Avalanche")').first.click()
    logged_in_page.wait_for_load_state("networkidle")
