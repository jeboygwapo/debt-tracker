"""SMOKE-021 — static asset wiring.

If chart.min.js stops being served, every dashboard chart silently breaks.
"""

import pytest


pytestmark = [pytest.mark.smoke, pytest.mark.anyio]


async def test_smoke_021_static_chart_js_served(smoke_client):
    r = await smoke_client.get("/static/chart.min.js")
    assert r.status_code == 200
    # Cheap content sniff — Chart.js bundles begin with a license banner that
    # always mentions either "Chart.js" or "chartjs". Either is acceptable.
    head = r.text[:512].lower()
    assert "chart" in head
