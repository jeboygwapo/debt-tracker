"""E2E test fixtures.

Tests in ``tests/e2e/`` drive a real Chromium browser against a
dockerised debt-tracker stack (Postgres + app via ``Dockerfile``).

Required env vars (DevOps wires these in the CI job):

    E2E_BASE_URL   default ``http://localhost:5050``
    CI_ADMIN_USER  matches the admin seeded by ``scripts/init_db.py``
    CI_ADMIN_PASS  matches the password seeded by ``scripts/init_db.py``

The fixtures here intentionally do NOT spin up the docker compose stack —
that is DevOps's job and keeps responsibilities split. Tests assume the
stack is reachable at ``E2E_BASE_URL``.

We pin to Chromium-only (Firefox/WebKit add ~250 MB install + ~30 s with
no extra signal for our flows). To run locally:

    docker compose -f tests/e2e/docker-compose.test.yml up -d
    python3 -m playwright install --with-deps chromium
    python3 -m pytest tests/e2e/ -m e2e -v
    docker compose -f tests/e2e/docker-compose.test.yml down -v
"""

from __future__ import annotations

import os
import time
from typing import Iterator

import pytest


E2E_BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:5050").rstrip("/")
CI_ADMIN_USER = os.environ.get("CI_ADMIN_USER", "ci_admin")
CI_ADMIN_PASS = os.environ.get("CI_ADMIN_PASS", "CiAdminPass1234!")


# ── Collection gate — only run when explicitly requested ──────────────────────
#
# Pytest collects every file matching ``test_*.py`` by default. That would
# pull the E2E suite into ``python3 -m pytest tests/`` runs even when
# pytest-playwright is not installed and no compose stack is up. To keep
# the unit/integration/smoke loops cheap, the e2e package is collected
# only when the user explicitly opts in via either:
#
#   * ``-m e2e``                  (marker selection includes e2e)
#   * ``E2E_RUN=1``               (env var, useful for ``pytest tests/e2e``)
#   * Path-targeted invocation    (``pytest tests/e2e/...``)
#
# Anything else → ``collect_ignore`` returns the directory so pytest skips
# it before any fixture runs. This also dodges the ``pytest-playwright``
# import error on environments that don't have it installed.


def _e2e_explicitly_requested(config) -> bool:
    if os.environ.get("E2E_RUN") == "1":
        return True
    marker_expr = config.getoption("-m") or ""
    if "e2e" in marker_expr:
        return True
    # Path-targeted: ``pytest tests/e2e/...``
    for arg in config.args:
        if "tests/e2e" in str(arg).replace("\\", "/"):
            return True
    return False


def pytest_collection_modifyitems(config, items):
    """Skip every collected e2e test when not explicitly requested.

    We can't rely on ``collect_ignore`` here because this conftest only loads
    after pytest enters the e2e directory. Instead we deselect collected
    items so the fixture chain never fires.
    """
    if _e2e_explicitly_requested(config):
        return

    skipped: list = []
    remaining: list = []
    for item in items:
        if "tests/e2e" in str(item.fspath).replace("\\", "/"):
            skipped.append(item)
        else:
            remaining.append(item)

    if skipped:
        config.hook.pytest_deselected(items=skipped)
        items[:] = remaining


# ── Chromium-only override (pytest-playwright hooks) ──────────────────────────


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):  # noqa: F811 — pytest-playwright fixture
    return {**browser_type_launch_args, "headless": True}


# ── App-readiness gate ────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _wait_for_app() -> None:
    """Block until the app's ``/api/healthz`` answers 200.

    Compose brings the stack up in the background; without this gate the
    first browser navigation can race the migrations / uvicorn boot.
    """
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + 60  # 60 s budget
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{E2E_BASE_URL}/api/healthz", timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_err = exc
        time.sleep(1)

    raise RuntimeError(
        f"E2E app not reachable at {E2E_BASE_URL}/api/healthz within 60s. "
        f"Last error: {last_err!r}. Is the docker compose stack up?"
    )


# ── Public fixtures the tests use ─────────────────────────────────────────────


@pytest.fixture
def base_url() -> str:
    return E2E_BASE_URL


@pytest.fixture
def admin_credentials() -> dict[str, str]:
    return {"username": CI_ADMIN_USER, "password": CI_ADMIN_PASS}


@pytest.fixture
def logged_in_page(page, base_url, admin_credentials):
    """Login and return the ready-to-use Playwright ``page`` on the dashboard."""
    page.goto(f"{base_url}/login")
    page.fill('input[name="username"]', admin_credentials["username"])
    page.fill('input[name="password"]', admin_credentials["password"])
    page.click('button[type="submit"]')
    # Either we are at /, /debts (new user), or /welcome flow has consumed us.
    page.wait_for_load_state("networkidle")
    return page


@pytest.fixture
def _seed_debts(logged_in_page, base_url):
    """Ensure at least one debt exists and OFW mode is active.

    Tests that fill ``d_0_*`` fields on ``/add`` require the debt row inputs
    to render. Tests that assert ``PHP Received`` require OFW mode. This
    fixture handles both preconditions via the UI so the test session matches
    production behaviour.

    Usage: request ``_seed_debts`` explicitly in tests that need it.
    """
    page = logged_in_page

    # ── Step 1: create a seed debt via the /debts form ------------------
    page.goto(f"{base_url}/debts")
    page.wait_for_load_state("networkidle")

    # Only create when no debt rows are present to keep the fixture idempotent.
    if page.locator("table tbody tr").count() == 0:
        page.click('button:has-text("+ Add Debt")')
        page.fill('input[name="name"]', "Seed Card")
        page.select_option('select[name="type"]', "credit_card")
        page.fill('input[name="apr_monthly_pct"]', "2.5")
        page.click('button:has-text("Save")')
        page.wait_for_load_state("networkidle")

    # ── Step 2: enable OFW mode if not already active -------------------
    page.goto(f"{base_url}/settings")
    page.wait_for_load_state("networkidle")
    settings_html = page.content()

    # The mode toggle button text is "Switch to Budget Mode" when OFW is ON,
    # and "Switch to OFW Mode" (or similar) when OFW is OFF. Enable only if off.
    if "Switch to OFW Mode" in settings_html or "ofw_mode" not in settings_html.lower():
        ofw_toggle = page.locator('form[action="/settings"] button[name="action"][value="mode"]').first
        if ofw_toggle.count() > 0:
            ofw_toggle.click()
            page.wait_for_load_state("networkidle")

    return page
