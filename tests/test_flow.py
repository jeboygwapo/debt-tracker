import pytest

from tests.conftest import get_csrf_token


@pytest.mark.anyio
async def test_flow_page_loads(authed_client):
    r = await authed_client.get("/flow")
    assert r.status_code == 200
    assert "Cash Flow" in r.text or "cash flow" in r.text.lower()


@pytest.mark.anyio
async def test_flow_allocate_unauthenticated_redirects(client):
    token = await get_csrf_token(client, "/login")
    r = await client.post(
        "/flow/allocate",
        data={"goal_id": "1", "amount": "100", "csrf_token": token},
        follow_redirects=False,
    )
    assert r.status_code in (302, 303)


@pytest.mark.anyio
async def test_flow_allocate_bumps_goal_current(authed_client):
    from app.db.base import AsyncSessionLocal
    from app.db.crud import create_goal, get_goal_by_id, get_user_by_username, delete_goal

    async with AsyncSessionLocal() as db:
        admin = await get_user_by_username(db, "testadmin")
        goal = await create_goal(
            db, user_id=admin.id, name="FlowTestGoal",
            target_php=10000, current_php=500,
            monthly_alloc_php=200, target_date=None,
        )
        goal_id = goal.id

    try:
        token = await get_csrf_token(authed_client, "/goals")
        r = await authed_client.post(
            "/flow/allocate",
            data={"goal_id": str(goal_id), "amount": "300", "csrf_token": token},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/flow" in r.headers["location"]

        async with AsyncSessionLocal() as db:
            g = await get_goal_by_id(db, goal_id, admin.id)
            assert float(g.current_php) == 800.0
    finally:
        async with AsyncSessionLocal() as db:
            await delete_goal(db, goal_id, admin.id)


@pytest.mark.anyio
async def test_flow_allocate_rejects_negative_amount(authed_client):
    token = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post(
        "/flow/allocate",
        data={"goal_id": "1", "amount": "-100", "csrf_token": token},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "must+be+positive" in r.headers["location"] or "positive" in r.headers["location"]


@pytest.mark.anyio
async def test_flow_allocate_unknown_goal(authed_client):
    token = await get_csrf_token(authed_client, "/goals")
    r = await authed_client.post(
        "/flow/allocate",
        data={"goal_id": "999999", "amount": "100", "csrf_token": token},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "not+found" in r.headers["location"] or "not%20found" in r.headers["location"]
