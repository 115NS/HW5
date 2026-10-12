"""MCP server: Problem 3 tools unchanged, Problem 5 tools match the database."""

import asyncio
import json
import sqlite3

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from conftest import TESTS
from server import mcp, _connect

PROBLEM3_TOOLS = {"check_stock", "get_rent_due", "quote_bulk_order"}
PROBLEM5_TOOLS = {"list_open_tickets", "get_ticket", "get_cash_position", "get_invoice", "list_open_invoices",
                  "list_payments", "list_vendors", "project_cash_balance"}
PROBLEM7_TOOLS = {"list_tickets"}  # dashboard API only; no agent is given it


def call(name, args=None):
    async def go():
        async with Client(mcp) as c:
            return (await c.call_tool(name, args or {})).data
    return asyncio.run(go())


def test_tool_list():
    async def go():
        async with Client(mcp) as c:
            return {t.name for t in await c.list_tools()}
    assert asyncio.run(go()) == PROBLEM3_TOOLS | PROBLEM5_TOOLS | PROBLEM7_TOOLS


@pytest.mark.parametrize("case", json.loads((TESTS / "baseline_problem3_tools.json").read_text()),
                         ids=lambda c: f"{c['tool']}-{c['args']}")
def test_problem3_tools_unchanged(case):
    assert call(case["tool"], case["args"]) == case["result"]


def test_server_connection_is_read_only():
    with _connect() as conn, pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("UPDATE cash_accounts SET balance = 0")


def test_tickets_match_db(db):
    open_rows = db.execute("SELECT * FROM tickets WHERE status='open' ORDER BY created_at, id").fetchall()
    res = call("list_open_tickets")
    assert res["count"] == len(open_rows) == 3
    assert res["tickets"] == [dict(r) for r in open_rows]
    assert res["desk_date"] == db.execute("SELECT date_today FROM desk").fetchone()[0]
    for row in open_rows:
        assert call("get_ticket", {"ticket_id": row["id"]})["ticket"] == dict(row)
    assert call("get_ticket", {"ticket_id": 999})["found"] is False


def test_cash_invoices_payments_vendors_match_db(db):
    cash = db.execute("SELECT name, balance, date FROM cash_accounts").fetchall()
    res = call("get_cash_position")
    assert res["accounts"] == [{"account": r["name"], "balance": r["balance"], "as_of": r["date"]} for r in cash]
    assert res["total_balance"] == sum(r["balance"] for r in cash)

    inv = db.execute("SELECT * FROM invoices WHERE id=501").fetchone()
    vendor = db.execute("SELECT * FROM vendors WHERE id=?", (inv["vendor_id"],)).fetchone()
    got = call("get_invoice", {"invoice_id": 501})["invoice"]
    assert (got["amount"], got["due_date"], got["status"], got["vendor_name"]) == (inv["amount"], inv["due_date"], inv["status"], vendor["name"])
    assert got["days_until_due"] == -3 and got["overdue"] is True  # due 2026-08-28, desk 2026-08-31

    open_total = db.execute("SELECT COALESCE(SUM(amount),0) FROM invoices WHERE status='open'").fetchone()[0]
    assert call("list_open_invoices")["total_open"] == open_total

    assert call("list_payments")["count"] == db.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    assert call("list_payments", {"kind": "rent", "ref_id": 1})["payments"] == []

    assert call("list_vendors")["vendors"] == [dict(r) for r in db.execute("SELECT * FROM vendors ORDER BY id")]
    assert [v["name"] for v in call("list_vendors", {"specialty": "MUGS"})["vendors"]] == ["Elm City Gifts"]


def test_project_cash_balance(db):
    balance = db.execute("SELECT balance FROM cash_accounts WHERE name='checking'").fetchone()[0]
    ok = call("project_cash_balance", {"outflows": [{"label": "rent", "amount": 2400}, {"label": "inv 501", "amount": 840}]})
    assert ok["starting_balance"] == balance
    assert [s["balance_after"] for s in ok["steps"]] == [balance - 2400, balance - 3240]
    assert ok["stays_non_negative"] is True and ok["first_negative"] is None

    bad = call("project_cash_balance", {"outflows": [{"label": "rent", "amount": 2400}, {"label": "big", "amount": 1001}]})
    assert bad["stays_non_negative"] is False and bad["first_negative"] == "big"

    assert call("project_cash_balance", {"outflows": [], "account": "savings"})["found"] is False
    with pytest.raises(ToolError):
        call("project_cash_balance", {"outflows": [{"label": "refund?", "amount": -50}]})


def test_list_tickets_matches_db(db):
    rows = db.execute("SELECT * FROM tickets ORDER BY created_at, id").fetchall()
    assert call("list_tickets")["tickets"] == [dict(r) for r in rows]
    assert call("list_tickets", {"status": "resolved"})["count"] == 0


def test_no_agent_has_list_tickets():
    from backend.agents import AGENT_MCP_TOOLS
    assert all("list_tickets" not in tools for tools in AGENT_MCP_TOOLS.values())


def test_db_override_can_never_point_at_the_original(monkeypatch):
    from conftest import ORIGINAL_DB
    monkeypatch.setenv("CAMPUS_CUSTOMS_DB", str(ORIGINAL_DB))
    with pytest.raises(PermissionError):
        _connect()
