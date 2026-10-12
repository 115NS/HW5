"""The five-agent team end to end: real MCP server over stdio, scripted models (no Portkey)."""

import asyncio
from collections import Counter

import pytest

from backend.agents import AGENT_MCP_TOOLS, MAX_DELEGATIONS_PER_TICKET, Team
from scripted_team import PLANNERS, scripted_models


def run(models, ticket_ids, audit_path):
    async def go():
        async with Team(models, audit_path=audit_path) as team:
            return [await team.resolve(t) for t in ticket_ids], team
    return asyncio.run(go())


@pytest.fixture(scope="module")
def batch(tmp_path_factory):
    path = tmp_path_factory.mktemp("audit") / "audit_trail.json"
    resolutions, team = run(scripted_models(), [101, 102, 103], path)
    return {r.ticket_id: r for r in resolutions}, team.audit.entries(), team


def facts(res):
    return {f.label: f.value for f in res.key_facts}


def test_three_tickets_resolved_as_proposals(batch):
    res, _, _ = batch
    assert set(res) == {101, 102, 103}
    for r in res.values():
        assert r.approval_status == "pending_human_approval"
        assert all(c.passed for c in r.rule_checks), [c for c in r.rule_checks if not c.passed]
        assert all(a.status == "proposed" for a in r.proposed_actions)


def test_101_out_of_stock_tee(batch, db):
    r = batch[0][101]
    s = db.execute("SELECT qty FROM inventory WHERE sku='CC-TEE-WHITE' AND size='S'").fetchone()[0]
    f = facts(r)
    assert f["CC-TEE-WHITE S on hand"] == str(s) == "0"
    assert f["other sizes"] == "M 5, L 3, XL 2"
    assert f["invoice 501"].startswith("$840.00 open, due 2026-08-28 (-3 days)")
    assert r.delegated_to == ["customer_service", "accounting"]
    assert r.customer_reply_draft.to == "Tauhid Zaman" and r.customer_reply_draft.sent is False


def test_102_rent_reviewed_without_paying(batch, db):
    r = batch[0][102]
    lease = db.execute("SELECT monthly_rent, next_due FROM leases WHERE id=1").fetchone()
    pay = [a for a in r.proposed_actions if a.kind == "payment"]
    assert len(pay) == 1 and pay[0].amount == lease["monthly_rent"] == 2400.0
    assert pay[0].requires_human_approval and pay[0].status == "proposed"
    assert facts(r)["rent due"] == f"$2,400.00 on {lease['next_due']} (2 days)"
    assert facts(r)["cash after rent + open invoices"] == "$160.00"
    assert r.customer_reply_draft is None
    assert db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0  # nothing was paid


def test_103_bulk_hoodies(batch, db):
    r = batch[0][103]
    m = db.execute("SELECT qty FROM inventory WHERE sku='CC-HOOD-NAVY' AND size='M'").fetchone()[0]
    f = facts(r)
    assert f["CC-HOOD-NAVY M on hand"] == str(m) == "8"
    assert f["shortfall"] == "12"
    assert f["0% off x20"] == "$1,160.00 revenue, $720.00 profit, 62.1% margin"
    assert f["10% off x20"] == "$1,044.00 revenue, $604.00 profit, 57.9% margin"
    assert r.customer_reply_draft.to == "Yale AI Club"


def test_delegation_paths(batch):
    _, entries, _ = batch
    paths = Counter((e["ticket_id"], e["delegation"]["from"], e["delegation"]["to"]) for e in entries if e["action"] == "delegation_request")
    assert paths == Counter({
        (101, "boss", "customer_service"): 1, (101, "customer_service", "inventory"): 1, (101, "boss", "accounting"): 1,
        (102, "boss", "facilities"): 1, (102, "facilities", "accounting"): 1,
        (103, "boss", "customer_service"): 1, (103, "customer_service", "inventory"): 1, (103, "customer_service", "accounting"): 1,
    })


def test_agents_only_use_their_own_mcp_tools(batch):
    _, entries, _ = batch
    for e in entries:
        if e["action"] == "tool_call" and e["agent"] != "guardrails":
            assert e["tool"]["name"] in AGENT_MCP_TOOLS[e["agent"]], e


def test_audit_trail_is_complete_and_intact(batch):
    _, entries, team = batch
    assert team.audit.verify() == (True, [])
    calls = [e for e in entries if e["action"] == "tool_call"]
    results = [e for e in entries if e["action"] == "tool_result"]
    assert len(calls) == len(results) > 0
    for t in (101, 102, 103):
        actions = [e["action"] for e in entries if e["ticket_id"] == t]
        assert actions[0] == "run_start" and actions[-1] == "run_end"
        for needed in ("agent_start", "model_step", "tool_call", "tool_result", "delegation_request",
                       "delegation_result", "agent_output", "guardrail_check", "resolution"):
            assert needed in actions, (t, needed)
    ends = [e for e in entries if e["action"] == "run_end"]
    assert all(e["approval_status"] == "pending_human_approval" for e in ends)
    assert {e["details"]["models"][0] for e in entries if e["action"] == "run_start"} == {"scripted-accounting"}


def test_repeat_delegation_is_reused_not_rerun(tmp_path):
    def boss(prompt, r):
        if len(r.get("delegate_to_facilities", [])) < 2:
            return ("delegate_to_facilities", {"task": "lease=1: confirm rent owed."})
        return PLANNERS["boss"](prompt, {**r, "get_ticket": r.get("get_ticket") or [{"ticket": {"type": "other", "requester": "x", "subject": "s"}}]})
    _, team = run(scripted_models(boss=boss), [102], tmp_path / "a.json")
    actions = [e["action"] for e in team.audit.entries()]
    assert actions.count("delegation_reused") == 1
    assert sum(1 for e in team.audit.entries() if e["action"] == "agent_start" and e["agent"] == "facilities") == 1


def test_delegation_limit_stops_runaway_loops(tmp_path):
    def boss(prompt, r):
        n = len(r.get("delegate_to_inventory", []))
        if n < MAX_DELEGATIONS_PER_TICKET + 2:
            return ("delegate_to_inventory", {"task": f"sku=CC-HAT-BLUE size=OS qty={n + 1}"})
        return ("final", {"ticket_id": 101, "ticket_type": "customer_order", "summary": "s", "recommended_option": "hold"})
    _, team = run(scripted_models(boss=boss), [101], tmp_path / "a.json")
    entries = team.audit.entries()
    assert sum(e["action"] == "delegation_request" for e in entries) == MAX_DELEGATIONS_PER_TICKET
    assert sum(e["action"] == "delegation_blocked" for e in entries) == 2


def test_specialist_failure_is_logged_and_boss_continues(tmp_path):
    def broken_inventory(prompt, r):
        raise RuntimeError("simulated model outage")
    resolutions, team = run(scripted_models(inventory=broken_inventory), [101], tmp_path / "a.json")
    entries = team.audit.entries()
    assert any(e["action"] == "error" and e["agent"] == "inventory" and "simulated model outage" in e["error"] for e in entries)
    assert any(e["action"] == "delegation_failed" and e["delegation"]["to"] == "inventory" for e in entries)
    assert entries[-1]["action"] == "run_end"
