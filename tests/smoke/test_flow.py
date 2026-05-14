"""SMOKE-026..029 — /flow page and /api/flow/suggestion endpoint.

Covers auth gate, page render, and AI suggestion contract.
"""

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_026_flow_page_authenticated(smoke_authed_client):
    """Authenticated user gets the Sankey flow page."""
    r = await smoke_authed_client.get("/flow")
    assert r.status_code == 200
    assert "flow" in r.text.lower() or "sankey" in r.text.lower() or "Income" in r.text


async def test_smoke_027_flow_suggestion_authenticated_no_key(smoke_authed_client):
    """Authed request to /api/flow/suggestion returns structured JSON.

    Smoke environment has no OpenAI key — expect either an error payload
    or a cached html payload. Never a bare 500.
    """
    r = await smoke_authed_client.get("/api/flow/suggestion")
    assert r.status_code in (200, 429)
    body = r.json()
    assert "html" in body or "error" in body


async def test_smoke_028_flow_page_unauthenticated(smoke_client_no_redirect):
    """Unauthenticated GET /flow redirects to /welcome."""
    r = await smoke_client_no_redirect.get("/flow")
    assert r.status_code == 302
    assert "/welcome" in r.headers["location"]


async def test_smoke_029_flow_suggestion_unauthenticated(smoke_client):
    """Unauthenticated /api/flow/suggestion returns 401 JSON."""
    r = await smoke_client.get("/api/flow/suggestion")
    assert r.status_code == 401
    body = r.json()
    assert body.get("error") == "Unauthorized"
