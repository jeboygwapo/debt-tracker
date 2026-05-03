"""E2E — debt CRUD with type-name confirmation on delete.

Create a debt, edit it, verify the delete button is disabled until the
exact name is typed in the confirmation input, then delete it.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_create_edit_delete_debt(logged_in_page, base_url):
    debt_name = "E2E Test Card"

    # ── Create
    logged_in_page.goto(f"{base_url}/debts")
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.click('button:has-text("+ Add Debt")')
    logged_in_page.fill('input[name="name"]', debt_name)
    logged_in_page.select_option('select[name="type"]', "credit_card")
    logged_in_page.fill('input[name="apr_monthly_pct"]', "3.0")
    logged_in_page.click('button:has-text("Save")')
    logged_in_page.wait_for_load_state("networkidle")
    assert debt_name in logged_in_page.content()

    # ── Edit
    edit_link = logged_in_page.locator(f'tr:has-text("{debt_name}") a:has-text("Edit")').first
    edit_link.click()
    logged_in_page.wait_for_load_state("networkidle")
    logged_in_page.fill('input[name="apr_monthly_pct"]', "4.5")
    logged_in_page.click('button:has-text("Save Changes")')
    logged_in_page.wait_for_load_state("networkidle")
    assert "Saved" in logged_in_page.content() or "4.5" in logged_in_page.content()

    # ── Delete with type-name confirmation
    logged_in_page.click('button:has-text("Delete This Debt")')
    confirm_btn = logged_in_page.locator('#confirm-delete-btn')
    # Button must start disabled
    assert confirm_btn.is_disabled()

    logged_in_page.fill('#confirm-name-input', debt_name)
    # Now button becomes enabled — small wait for JS event handler
    logged_in_page.wait_for_function(
        "() => !document.getElementById('confirm-delete-btn').disabled"
    )
    confirm_btn.click()
    logged_in_page.wait_for_load_state("networkidle")

    # Verify it is gone
    assert debt_name not in logged_in_page.content()
