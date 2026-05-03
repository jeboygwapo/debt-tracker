"""SMOKE-018 — unauthenticated /api/analysis must return 401.

Public-facing JSON endpoints must never leak data without a session.
"""

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_018_api_analysis_unauthenticated_401(smoke_client):
    r = await smoke_client.get("/api/analysis")
    assert r.status_code == 401
    body = r.json()
    assert body.get("error") == "Unauthorized"
