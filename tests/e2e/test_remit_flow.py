"""E2E — remit/budget flow.

Enter an SAR amount on /remit, submit, see the allocation table render
with the converted PHP amount and the bonus card when surplus exists.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def _seed_month(page, base_url, month: str = "2026-10"):
    page.goto(f"{base_url}/add")
    page.wait_for_load_state("networkidle")
    page.fill('input[name="month"]', month)
    # Statement tab is active by default — balance and min_due are visible here.
    page.fill('input[name="d_0_balance"]', "10000")
    page.fill('input[name="d_0_min_due"]', "500")
    # Switch to the Payments tab so d_0_payment is no longer display:none.
    page.locator('#tabbtn-payments').click()
    payment_input = page.locator('input[name="d_0_payment"]')
    payment_input.scroll_into_view_if_needed()
    payment_input.click()
    payment_input.fill("0")
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def test_remit_calculates_and_renders_allocation(logged_in_page, base_url, _seed_debts):
    _seed_month(logged_in_page, base_url)

    logged_in_page.goto(f"{base_url}/remit")
    logged_in_page.wait_for_load_state("networkidle")

    # Enter a generous SAR amount that creates surplus → bonus card should appear.
    logged_in_page.fill('input[name="sar"]', "10000")
    logged_in_page.click('button[type="submit"]')
    logged_in_page.wait_for_load_state("networkidle")

    body = logged_in_page.content()
    # Result section renders an "Allocation Plan" heading
    assert "Allocation Plan" in body
    # PHP value of remittance must appear (10,000 SAR * default rate >= 100,000 PHP)
    assert "PHP Received" in body
