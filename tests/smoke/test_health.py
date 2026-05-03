"""SMOKE-001 — health endpoint contract.

Liveness probe used by Fly.io and any future K8s deployment. Must always
respond with 200 + ``{"status": "ok"}`` when the DB ping succeeds.
"""

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_001_healthz_ok(smoke_client):
    r = await smoke_client.get("/api/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
