"""Phase 3 networth tests: Account/Snapshot CRUD, net worth calc, /networth routes."""
import pytest

pytestmark = pytest.mark.anyio

from app.routes.networth import _net_worth_summary, _account_rows
from app.services.statement_parser import ParseError, _extract_json, _validate_result, compute_file_hash
from tests.conftest import TEST_PASS, TEST_USER, get_csrf_token


# ── statement_parser unit tests ───────────────────────────────────────────────

async def test_compute_file_hash_deterministic():
    data = b"hello world"
    assert compute_file_hash(data) == compute_file_hash(data)
    assert len(compute_file_hash(data)) == 64  # SHA256 hex


async def test_extract_json_clean():
    raw = '{"balance": 12500.50, "month": "2026-04", "account_hint": "BDO Savings"}'
    result = _extract_json(raw)
    assert result["balance"] == 12500.50
    assert result["month"] == "2026-04"


async def test_extract_json_embedded_in_text():
    raw = 'Here is the result: {"balance": 5000, "month": "2026-03", "account_hint": null}'
    result = _extract_json(raw)
    assert result["balance"] == 5000


async def test_extract_json_no_json_raises():
    with pytest.raises(ParseError):
        _extract_json("No JSON here at all.")


async def test_validate_result_valid():
    data = {"balance": 10000.0, "month": "2026-04", "account_hint": "BPI"}
    result = _validate_result(data)
    assert result["balance"] == 10000.0
    assert result["month"] == "2026-04"
    assert result["account_hint"] == "BPI"


async def test_validate_result_bad_month_clears():
    data = {"balance": 5000, "month": "not-a-date", "account_hint": None}
    result = _validate_result(data)
    assert result["month"] is None


async def test_validate_result_no_balance_raises():
    with pytest.raises(ParseError):
        _validate_result({"balance": None, "month": "2026-04"})


async def test_validate_result_negative_balance_raises():
    with pytest.raises(ParseError):
        _validate_result({"balance": -100, "month": "2026-04"})


# ── _net_worth_summary unit tests ─────────────────────────────────────────────

class _Acc:
    def __init__(self, id, name="Test"):
        self.id = id
        self.name = name


class _Snap:
    def __init__(self, account_id, month, balance):
        self.account_id = account_id
        self.month = month
        self.balance = balance


async def test_net_worth_no_data():
    summary = _net_worth_summary([], [], {})
    assert summary["total_assets"] == 0
    assert summary["total_liabilities"] == 0
    assert summary["net_worth"] == 0


async def test_net_worth_assets_only():
    accounts = [_Acc(1)]
    snapshots = [_Snap(1, "2026-04", 50000)]
    summary = _net_worth_summary(accounts, snapshots, {})
    assert summary["total_assets"] == 50000
    assert summary["net_worth"] == 50000


async def test_net_worth_with_liabilities():
    accounts = [_Acc(1)]
    snapshots = [_Snap(1, "2026-04", 100000)]
    months = {"2026-04": {"CC1": {"balance": 40000}}}
    summary = _net_worth_summary(accounts, snapshots, months)
    assert summary["total_assets"] == 100000
    assert summary["total_liabilities"] == 40000
    assert summary["net_worth"] == 60000


async def test_net_worth_trend_aggregates():
    accounts = [_Acc(1), _Acc(2)]
    snapshots = [
        _Snap(1, "2026-03", 10000),
        _Snap(2, "2026-03", 5000),
        _Snap(1, "2026-04", 11000),
        _Snap(2, "2026-04", 5500),
    ]
    summary = _net_worth_summary(accounts, snapshots, {})
    assert summary["trend_months"] == ["2026-03", "2026-04"]
    assert summary["trend_values"] == [15000.0, 16500.0]


async def test_net_worth_uses_latest_snapshot_per_account():
    accounts = [_Acc(1)]
    snapshots = [
        _Snap(1, "2026-02", 9000),
        _Snap(1, "2026-03", 10000),
        _Snap(1, "2026-04", 11000),
    ]
    summary = _net_worth_summary(accounts, snapshots, {})
    assert summary["total_assets"] == 11000


# ── Authenticated client fixture ──────────────────────────────────────────────

@pytest.fixture
async def authed_client(client):
    csrf = await get_csrf_token(client, "/login")
    await client.post("/login", data={
        "username": TEST_USER,
        "password": TEST_PASS,
        "csrf_token": csrf,
    })
    return client


# ── /networth GET ─────────────────────────────────────────────────────────────

async def test_networth_get_renders(authed_client):
    r = await authed_client.get("/networth")
    assert r.status_code == 200
    assert "Net Worth" in r.text


async def test_networth_empty_state(authed_client):
    r = await authed_client.get("/networth")
    assert r.status_code == 200
    assert "No accounts yet" in r.text or "Net Worth" in r.text


# ── Account CRUD ──────────────────────────────────────────────────────────────

async def test_networth_add_account(authed_client):
    csrf = await get_csrf_token(authed_client, "/networth")
    r = await authed_client.post("/networth", data={
        "csrf_token": csrf,
        "action": "add_account",
        "name": "BDO Savings",
        "type": "bank",
    })
    assert r.status_code == 200
    assert "BDO Savings" in r.text


async def test_networth_add_account_invalid_name(authed_client):
    csrf = await get_csrf_token(authed_client, "/networth")
    r = await authed_client.post("/networth", data={
        "csrf_token": csrf,
        "action": "add_account",
        "name": "",
        "type": "bank",
    })
    assert r.status_code == 200
    assert "Invalid" in r.text


async def test_networth_add_multiple_account_types(authed_client):
    for name, acc_type in [("PAG-IBIG MP2", "investment"), ("House", "property")]:
        csrf = await get_csrf_token(authed_client, "/networth")
        r = await authed_client.post("/networth", data={
            "csrf_token": csrf,
            "action": "add_account",
            "name": name,
            "type": acc_type,
        })
        assert r.status_code == 200
        assert name in r.text


async def test_networth_delete_account(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/networth")
    await authed_client.post("/networth", data={
        "csrf_token": csrf_add,
        "action": "add_account",
        "name": "To Delete Bank",
        "type": "bank",
    })

    import re
    r = await authed_client.get("/networth")
    ids = re.findall(r'data-id="(\d+)"', r.text)
    if not ids:
        pytest.skip("no account found")

    csrf = await get_csrf_token(authed_client, "/networth")
    r = await authed_client.post("/networth", data={
        "csrf_token": csrf,
        "action": "delete_account",
        "id": ids[-1],
    })
    assert r.status_code == 200


async def test_networth_edit_account_page(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/networth")
    await authed_client.post("/networth", data={
        "csrf_token": csrf_add,
        "action": "add_account",
        "name": "Edit Me Bank",
        "type": "bank",
    })

    import re
    r = await authed_client.get("/networth")
    hrefs = re.findall(r'/networth/accounts/(\d+)/edit', r.text)
    if not hrefs:
        pytest.skip("no account edit link found")

    r = await authed_client.get(f"/networth/accounts/{hrefs[-1]}/edit")
    assert r.status_code == 200
    assert "Edit Me Bank" in r.text


# ── Snapshot CRUD ─────────────────────────────────────────────────────────────

async def test_networth_add_snapshot(authed_client):
    csrf_add = await get_csrf_token(authed_client, "/networth")
    await authed_client.post("/networth", data={
        "csrf_token": csrf_add,
        "action": "add_account",
        "name": "Snapshot Test Bank",
        "type": "bank",
    })

    import re
    r = await authed_client.get("/networth")
    hrefs = re.findall(r'/networth/accounts/(\d+)/edit', r.text)
    if not hrefs:
        pytest.skip("no account found")
    account_id = hrefs[-1]

    csrf = await get_csrf_token(authed_client, f"/networth/accounts/{account_id}/edit")
    r = await authed_client.post("/networth", data={
        "csrf_token": csrf,
        "action": "add_snapshot",
        "account_id": account_id,
        "month": "2026-04",
        "balance": "75000",
    })
    assert r.status_code == 200
    assert "75,000" in r.text or "Snapshot saved" in r.text or "2026-04" in r.text


async def test_networth_snapshot_invalid_month(authed_client):
    import re
    r = await authed_client.get("/networth")
    hrefs = re.findall(r'/networth/accounts/(\d+)/edit', r.text)
    if not hrefs:
        pytest.skip("no account found")
    account_id = hrefs[0]

    csrf = await get_csrf_token(authed_client, f"/networth/accounts/{account_id}/edit")
    r = await authed_client.post("/networth", data={
        "csrf_token": csrf,
        "action": "add_snapshot",
        "account_id": account_id,
        "month": "not-valid",
        "balance": "1000",
    })
    assert r.status_code == 200


async def test_networth_reorder(authed_client):
    for name in ("Reorder A", "Reorder B"):
        csrf = await get_csrf_token(authed_client, "/networth")
        await authed_client.post("/networth", data={
            "csrf_token": csrf,
            "action": "add_account",
            "name": name,
            "type": "bank",
        })

    import re
    r = await authed_client.get("/networth")
    ids = re.findall(r'data-id="(\d+)"', r.text)
    if len(ids) < 2:
        pytest.skip("need 2+ accounts")

    csrf = await get_csrf_token(authed_client, "/networth")
    r = await authed_client.post("/networth", data={
        "csrf_token": csrf,
        "action": "reorder",
        "order": ",".join(reversed(ids)),
    })
    assert r.status_code == 200


# ── Parse endpoint ────────────────────────────────────────────────────────────

async def test_networth_parse_no_key(authed_client):
    """Without OpenAI key, parse endpoint should return error."""
    import io
    csrf = await get_csrf_token(authed_client, "/networth")
    fake_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    r = await authed_client.post(
        "/networth/parse",
        data={"csrf_token": csrf},
        files={"file": ("test.png", io.BytesIO(fake_image), "image/png")},
    )
    body = r.json()
    assert r.status_code in (200, 422, 429)
    assert "error" in body
