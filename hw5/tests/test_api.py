"""Problem 7 routes, end to end with FastAPI's TestClient.

Each test gets its own temp copy of the working DB (via CAMPUS_CUSTOMS_DB),
its own audit trail and proposal store, and scripted models (no Portkey).
The autouse fixture in conftest asserts the real DB files never change.
"""

import asyncio
import hashlib
import json
import shutil
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from backend import proposals
from backend.agents import AgentNotConfigured
from backend.main import Settings, create_app
from conftest import ORIGINAL_DB
from scripted_team import scripted_models

RUN_ID = "abc123def456"  # a hand-made stored proposal for approval tests


@pytest.fixture
def env(tmp_path, monkeypatch):
    db = tmp_path / "campus_customs_test.db"
    shutil.copyfile(ORIGINAL_DB, db)  # start from the original values, whatever state the working DB is in
    monkeypatch.setenv("CAMPUS_CUSTOMS_DB", str(db))
    settings = Settings(audit_path=tmp_path / "audit_trail.json", proposals_path=tmp_path / "proposed_resolutions.json",
                        models_factory=scripted_models)
    with TestClient(create_app(settings)) as client:
        yield client, db, settings


def q(db, sql, *args):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def stored_proposal(settings, ticket_id, actions):
    proposals.save(settings.proposals_path, ticket_id, {
        "ticket_id": ticket_id, "ticket_type": "x", "summary": "hand-made test proposal", "recommended_option": "r",
        "proposed_actions": [{"requires_human_approval": True, "status": "proposed", "payee": None, "ref": None, **a} for a in actions],
        "approval_status": "pending_human_approval", "run_id": RUN_ID,
    })


def approve(client, ticket_id, index, amount, **extra):
    body = {"ticket_id": ticket_id, "action_id": f"{RUN_ID}:{index}", "amount": amount, "approved_by": "Navya Sharma", "confirm": True, **extra}
    return client.post("/api/approvals", json=body)


# --- reads ---------------------------------------------------------------------


def test_health_reports_config_without_the_key(env):
    client, *_ = env
    body = client.get("/api/health").json()
    assert body["model"] == "gpt-6-luna" and body["database"] == "campus_customs_test.db"
    assert set(body) == {"status", "model", "portkey_key_configured", "database"}


def test_list_tickets(env):
    client, db, _ = env
    body = client.get("/api/tickets").json()
    assert [t["id"] for t in body["tickets"]] == [101, 102, 103]
    assert all(t["status"] == "open" and t["proposal"] is None and t["run"] is None for t in body["tickets"])
    assert body["tickets"][2]["qty"] == 20 and body["desk_date"] == "2026-08-31"


def test_ticket_id_validation(env):
    client, *_ = env
    assert client.get("/api/tickets/999").status_code == 404
    assert client.get("/api/tickets/0").status_code == 422
    assert client.get("/api/tickets/abc").status_code == 422
    assert client.post("/api/tickets/999/run", json={"wait": True}).status_code == 404
    assert client.post("/api/tickets/101/run", json={"wait": True, "extra": 1}).status_code == 422


def test_cash_matches_db(env):
    client, db, _ = env
    body = client.get("/api/cash").json()
    assert body["balance"] == q(db, "SELECT balance FROM cash_accounts WHERE name='checking'")[0][0] == 3400.0


# --- agent runs ------------------------------------------------------------------


def test_run_agents_and_events(env):
    client, db, settings = env
    r = client.post("/api/tickets/102/run", json={"wait": True})
    assert r.status_code == 200, r.text
    prop = r.json()["proposal"]
    assert r.json()["run"]["status"] == "completed" and prop["run_id"]
    pay = [a for a in prop["proposed_actions"] if a["kind"] == "payment"]
    assert len(pay) == 1 and pay[0]["amount"] == 2400.0 and pay[0]["approvable"] and pay[0]["action_id"] == f"{prop['run_id']}:0"
    assert q(db, "SELECT COUNT(*) FROM payments")[0][0] == 0  # the run itself pays nothing

    ev = client.get("/api/events", params={"ticket_id": 102}).json()
    actions = [e["action"] for e in ev["events"]]
    assert actions[-1] == "run_end" and "tool_call" in actions and "delegation_request" in actions
    assert any(e["agent"] == "facilities" and e["tool"] and e["tool"]["name"] == "get_rent_due" for e in ev["events"])
    assert all(e["message"] for e in ev["events"])
    newer = client.get("/api/events", params={"after_seq": ev["last_seq"]}).json()
    assert newer["count"] == 0 and newer["last_seq"] == ev["last_seq"]
    assert client.get("/api/events", params={"limit": 3}).json()["count"] == 3
    assert client.get("/api/events", params={"limit": 0}).status_code == 422

    listed = {t["id"]: t for t in client.get("/api/tickets").json()["tickets"]}
    assert listed[102]["proposal"]["approvable_actions"] == 1 and listed[102]["run"]["status"] == "completed"


def test_background_run_then_poll(env):
    client, *_ = env
    r = client.post("/api/tickets/101/run")
    assert r.status_code == 202 and r.json()["run"]["status"] == "running"
    for _ in range(100):
        run = client.get("/api/tickets/101").json()["run"]
        if run["status"] != "running":
            break
        time.sleep(0.1)
    assert run["status"] == "completed", run
    assert client.get("/api/tickets/101").json()["proposal"]["ticket_id"] == 101


def test_second_run_while_one_is_running_is_refused(env, tmp_path):
    client, _, settings = env

    async def slow(messages, info):
        await asyncio.sleep(1.5)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "ticket_id": 103, "ticket_type": "price_override", "summary": "s", "recommended_option": "hold"})])

    settings.models_factory = lambda: {**scripted_models(), "boss": FunctionModel(slow, model_name="slow-boss")}
    assert client.post("/api/tickets/103/run").status_code == 202
    second = client.post("/api/tickets/101/run", json={"wait": True})
    assert second.status_code == 409 and "already in progress" in second.json()["detail"]
    assert client.post("/api/reset", json={"confirm": True}).status_code == 409  # no reset mid-run
    for _ in range(60):
        if client.get("/api/tickets/103").json()["run"]["status"] != "running":
            break
        time.sleep(0.1)


def test_missing_portkey_key_gives_503(env):
    client, _, settings = env

    def no_key():
        raise AgentNotConfigured("PORTKEY_API_KEY is not set.")

    settings.models_factory = no_key
    r = client.post("/api/tickets/101/run", json={"wait": True})
    assert r.status_code == 503 and "PORTKEY_API_KEY" in r.json()["detail"]


# --- approvals ------------------------------------------------------------------


def test_approve_rent_from_a_real_run(env):
    client, db, settings = env
    prop = client.post("/api/tickets/102/run", json={"wait": True}).json()["proposal"]
    action = next(a for a in prop["proposed_actions"] if a["kind"] == "payment")
    body = {"ticket_id": 102, "action_id": action["action_id"], "amount": 2400.0, "approved_by": "Navya Sharma", "confirm": True}

    r = client.post("/api/approvals", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["payment_kind"], out["ref_id"], out["balance_before"], out["balance_after"]) == ("rent", 1, 3400.0, 1000.0)
    assert out["ticket_status"] == "resolved"
    assert q(db, "SELECT kind, ref_id, amount, account, approved_by FROM payments") == [("rent", 1, 2400.0, "checking", "Navya Sharma")]
    assert client.get("/api/cash").json()["balance"] == 1000.0
    assert {t["id"]: t["status"] for t in client.get("/api/tickets").json()["tickets"]}[102] == "resolved"

    again = client.post("/api/approvals", json=body)
    assert again.status_code == 409 and "Already approved" in again.json()["detail"]
    assert client.get("/api/cash").json()["balance"] == 1000.0
    assert client.post("/api/tickets/102/run", json={"wait": True}).status_code == 409  # resolved tickets can't be rerun

    ev = client.get("/api/events", params={"ticket_id": 102}).json()["events"]
    assert any(e["action"] == "human_approval" and e["agent"] == "human" for e in ev)
    assert any(e["action"] == "human_approval_rejected" for e in ev)


def test_approve_invoice_and_purchase_and_cash_floor(env):
    client, db, settings = env
    stored_proposal(settings, 101, [
        {"kind": "payment", "description": "Pay Bulldog Print Co", "amount": 840.0, "ref": "invoice 501"},
        {"kind": "restock_order", "description": "Reprint 12 hoodies", "amount": 2600.0},
        {"kind": "restock_order", "description": "Reprint 1 tee", "amount": 8.0},
    ])
    r = approve(client, 101, 0, 840.0, resolve_ticket=False)
    assert r.status_code == 200, r.text
    assert r.json()["payment_kind"] == "invoice" and r.json()["balance_after"] == 2560.0
    assert q(db, "SELECT status FROM invoices WHERE id=501")[0][0] == "paid"
    assert q(db, "SELECT status FROM tickets WHERE id=101")[0][0] == "open"  # resolve_ticket=False

    # $2,600 against $2,560 would go negative: refused, nothing changes.
    r = approve(client, 101, 1, 2600.0)
    assert r.status_code == 409 and "Insufficient cash" in r.json()["detail"]
    assert client.get("/api/cash").json()["balance"] == 2560.0
    assert q(db, "SELECT COUNT(*) FROM payments")[0][0] == 1

    r = approve(client, 101, 2, 8.0)
    assert r.status_code == 200 and r.json()["payment_kind"] == "purchase" and r.json()["balance_after"] == 2552.0


@pytest.mark.parametrize("change, status, fragment", [
    ({"confirm": False}, 422, "confirm"),
    ({"confirm": None}, 422, "confirm"),
    ({"approved_by": "boss"}, 422, "not an agent"),
    ({"approved_by": ""}, 422, "approved_by"),
    ({"amount": -5}, 422, "amount"),
    ({"action_id": "not-an-id"}, 422, "action_id"),
    ({"surprise": 1}, 422, "surprise"),
    ({"amount": 800.0}, 409, "does not match"),
    ({"action_id": f"{RUN_ID}:9"}, 404, "not in ticket"),
    ({"action_id": "ffffff000000:0"}, 409, "not in ticket"),
])
def test_approval_validation(env, change, status, fragment):
    client, db, settings = env
    stored_proposal(settings, 101, [{"kind": "payment", "description": "Pay Bulldog Print Co", "amount": 840.0, "ref": "invoice 501"}])
    body = {"ticket_id": 101, "action_id": f"{RUN_ID}:0", "amount": 840.0, "approved_by": "Navya Sharma", "confirm": True, **change}
    r = client.post("/api/approvals", json=body)
    assert r.status_code == status and fragment in json.dumps(r.json()), r.text
    assert q(db, "SELECT COUNT(*) FROM payments")[0][0] == 0 and client.get("/api/cash").json()["balance"] == 3400.0


def test_only_valid_payable_proposals_can_be_approved(env):
    client, db, settings = env
    stored_proposal(settings, 101, [
        {"kind": "customer_reply", "description": "Send reply", "amount": 1.0},
        {"kind": "payment", "description": "Blocked by guardrail", "amount": 840.0, "ref": "invoice 501", "status": "blocked_by_guardrail"},
        {"kind": "payment", "description": "Overstated invoice", "amount": 900.0, "ref": "invoice 501"},
        {"kind": "payment", "description": "Mystery payment", "amount": 10.0},
        {"kind": "payment", "description": "Pay rent", "amount": 2400.0, "ref": "lease 1"},  # lease isn't linked to #101
    ])
    assert approve(client, 101, 0, 1.0).status_code == 422
    assert approve(client, 101, 1, 840.0).status_code == 409
    r = approve(client, 101, 2, 900.0)
    assert r.status_code == 409 and "Invoice 501 is $840.00" in r.json()["detail"]
    assert approve(client, 101, 3, 10.0).status_code == 422
    assert approve(client, 101, 4, 2400.0).status_code == 409
    assert approve(client, 999, 0, 1.0).status_code == 404
    assert q(db, "SELECT COUNT(*) FROM payments")[0][0] == 0
    assert client.get("/api/tickets/101").json()["proposal"]["proposed_actions"][2]["approvable"] is True  # still pending


def test_no_proposal_means_nothing_to_approve(env):
    client, *_ = env
    r = approve(client, 103, 0, 10.0)
    assert r.status_code == 404 and "run the agents first" in r.json()["detail"]


# --- reset ------------------------------------------------------------------------


def test_reset_restores_original_values(env):
    client, db, settings = env
    stored_proposal(settings, 101, [{"kind": "payment", "description": "Pay Bulldog Print Co", "amount": 840.0, "ref": "invoice 501"}])
    assert approve(client, 101, 0, 840.0).status_code == 200
    assert client.get("/api/cash").json()["balance"] == 2560.0

    assert client.post("/api/reset", json={}).status_code == 422
    assert client.post("/api/reset", json={"confirm": False}).status_code == 422
    r = client.post("/api/reset", json={"confirm": True})
    assert r.status_code == 200 and r.json()["cash"]["balance"] == 3400.0
    assert hashlib.sha256(db.read_bytes()).hexdigest() == hashlib.sha256(ORIGINAL_DB.read_bytes()).hexdigest()
    assert q(db, "SELECT COUNT(*) FROM payments")[0][0] == 0
    assert q(db, "SELECT status FROM invoices WHERE id=501")[0][0] == "open"
    assert all(t["status"] == "open" for t in client.get("/api/tickets").json()["tickets"])
    # Approvals before the reset no longer count, so the proposal is approvable again.
    assert client.get("/api/tickets/101").json()["proposal"]["proposed_actions"][0]["approvable"] is True
    assert client.get("/api/events", params={"limit": 1}).json()["events"][0]["action"] == "database_reset"


def test_audit_trail_stays_intact(env):
    client, _, settings = env
    client.post("/api/tickets/102/run", json={"wait": True})
    stored_proposal(settings, 101, [{"kind": "payment", "description": "Pay Bulldog Print Co", "amount": 840.0, "ref": "invoice 501"}])
    approve(client, 101, 0, 999.0)
    approve(client, 101, 0, 840.0)
    client.post("/api/reset", json={"confirm": True})
    from backend.audit import AuditTrail
    assert AuditTrail(settings.audit_path).verify() == (True, [])


# --- write boundaries (added in the Problem 7 review) ------------------------------


def test_oversized_ids_are_rejected_before_reaching_the_database(env):
    client, *_ = env
    big = 10**20
    body = {"ticket_id": big, "action_id": f"{RUN_ID}:0", "amount": 1, "approved_by": "Navya Sharma", "confirm": True}
    r = client.post("/api/approvals", json=body)
    assert r.status_code == 422 and "ticket_id" in r.text
    assert client.get("/api/events", params={"ticket_id": big}).status_code == 422
    assert client.get(f"/api/tickets/{big}").status_code == 422


def test_ledger_itself_refuses_an_overdraw(env):
    """Even if the API checks were bypassed, the ledger's transaction refuses a negative balance."""
    from backend import ledger
    _, db, _ = env
    with pytest.raises(ledger.LedgerError) as exc:
        ledger.execute_approved_payment(kind="purchase", ref_id=101, amount=3400.01, approved_by="Navya Sharma",
                                        ticket_id=101, resolve_ticket=True)
    assert exc.value.status == 409
    assert q(db, "SELECT balance FROM cash_accounts")[0][0] == 3400.0
    assert q(db, "SELECT COUNT(*) FROM payments")[0][0] == 0
    assert q(db, "SELECT status FROM tickets WHERE id=101")[0][0] == "open"  # rolled back


def test_ledger_refuses_the_original_database(monkeypatch):
    from backend import ledger
    monkeypatch.setenv("CAMPUS_CUSTOMS_DB", str(ORIGINAL_DB))
    with pytest.raises(PermissionError):
        ledger.execute_approved_payment(kind="rent", ref_id=1, amount=1, approved_by="Navya Sharma", ticket_id=102, resolve_ticket=False)
    with pytest.raises(PermissionError):
        ledger.reset_working_db()


def test_only_the_ledger_writes_to_a_database():
    """Static check: one writable connection in the app (ledger.py); the MCP server is read-only;
    agents, guardrails, and models never reference the ledger."""
    import re
    from conftest import HW5
    files = {p.name: p.read_text() for p in [*(HW5 / "backend").glob("*.py"), HW5 / "mcp_server" / "server.py"]}
    connects = {name: re.findall(r"sqlite3\.connect\((.*)\)", src) for name, src in files.items()}
    assert {n for n, c in connects.items() if c} == {"ledger.py", "server.py"}
    assert all("mode=ro" in c for c in connects["server.py"])
    writes = {n for n, src in files.items() if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER)\b", src)}
    assert writes == {"ledger.py"}
    for name in ("agents.py", "guardrails.py", "models.py"):
        assert "ledger" not in files[name]


def test_cors_allows_the_vite_dev_origin_only(env):
    client, *_ = env
    def preflight(origin):
        return client.options("/api/approvals", headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                                         "Access-Control-Request-Headers": "content-type"})
    for ok in ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174"):
        r = preflight(ok)
        assert r.status_code == 200 and r.headers["access-control-allow-origin"] == ok, ok
    for bad in ("http://evil.example", "http://localhost:3000", "https://localhost:5173", "http://localhost:51730"):
        assert "access-control-allow-origin" not in preflight(bad).headers, bad
    assert client.get("/api/cash", headers={"Origin": "http://localhost:5173"}).headers["access-control-allow-origin"] == "http://localhost:5173"


# --- human approval of a resolution (Problem 9) -------------------------------------


def resolve(client, ticket_id, run_id=RUN_ID, **extra):
    body = {"run_id": run_id, "approved_by": "Navya Sharma", "confirm": True, **extra}
    return client.post(f"/api/tickets/{ticket_id}/resolve", json=body)


def test_resolve_marks_ticket_resolved_without_moving_money(env):
    client, db, settings = env
    stored_proposal(settings, 101, [{"kind": "customer_reply", "description": "Draft reply", "amount": None},
                                    {"kind": "substitute_offer", "description": "Offer size M", "amount": None}])
    r = resolve(client, 101, note="Customer offered size M")
    assert r.status_code == 200, r.text
    assert r.json()["ticket_status"] == "resolved" and r.json()["left_unpaid"] == [] and r.json()["paid"] == []
    assert q(db, "SELECT status FROM tickets WHERE id=101")[0][0] == "resolved"
    assert q(db, "SELECT balance FROM cash_accounts")[0][0] == 3400.0 and q(db, "SELECT COUNT(*) FROM payments")[0][0] == 0
    assert {t["id"]: t["status"] for t in client.get("/api/tickets").json()["tickets"]}[101] == "resolved"
    again = resolve(client, 101)
    assert again.status_code == 409 and "already resolved" in again.json()["detail"]
    ev = client.get("/api/events", params={"ticket_id": 101}).json()["events"]
    assert [e["action"] for e in ev][-2:] == ["human_resolution", "human_resolution_rejected"]


def test_resolve_requires_acknowledging_unpaid_payments(env):
    client, db, settings = env
    stored_proposal(settings, 101, [{"kind": "payment", "description": "Pay Bulldog Print Co", "amount": 840.0, "ref": "invoice 501"}])
    r = resolve(client, 101)
    assert r.status_code == 409 and "still awaiting approval" in r.json()["detail"]
    assert q(db, "SELECT status FROM tickets WHERE id=101")[0][0] == "open"
    r = resolve(client, 101, acknowledge_unpaid=True)
    assert r.status_code == 200 and r.json()["left_unpaid"][0]["amount"] == 840.0
    assert q(db, "SELECT status FROM invoices WHERE id=501")[0][0] == "open"  # nothing was paid
    assert q(db, "SELECT balance FROM cash_accounts")[0][0] == 3400.0


def test_resolve_after_paying_lists_the_payment(env):
    client, db, settings = env
    stored_proposal(settings, 101, [{"kind": "payment", "description": "Pay Bulldog Print Co", "amount": 840.0, "ref": "invoice 501"}])
    assert approve(client, 101, 0, 840.0, resolve_ticket=False).status_code == 200
    r = resolve(client, 101)
    assert r.status_code == 200 and r.json()["paid"][0]["amount"] == 840.0 and r.json()["left_unpaid"] == []


@pytest.mark.parametrize("change, status", [
    ({"confirm": False}, 422), ({"approved_by": "accounting"}, 422), ({"run_id": "nothex!"}, 422),
    ({"surprise": 1}, 422), ({"run_id": "ffffff000000"}, 409),
])
def test_resolve_validation(env, change, status):
    client, db, settings = env
    stored_proposal(settings, 102, [])
    assert resolve(client, 102, **change).status_code == status
    assert q(db, "SELECT status FROM tickets WHERE id=102")[0][0] == "open"


def test_resolve_needs_a_proposal_and_a_real_ticket(env):
    client, *_ = env
    assert resolve(client, 103).status_code == 404
    assert resolve(client, 999).status_code == 404
