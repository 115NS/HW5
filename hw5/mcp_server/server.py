"""Campus Customs operations MCP — Homework 5, Problems 3 and 5.

Read-only tools over ../data/campus_customs_new.db (the working copy; the
original data/campus_customs.db is never opened). No tool writes, pays,
orders, or sends anything.

Problem 3 (one per open ticket):
  check_stock          -> #101 customer_order (tee, size S)
  get_rent_due         -> #102 rent_notice (Chapel Street lease)
  quote_bulk_order     -> #103 price_override (20 hoodies, bulk discount)

Problem 5 (facts the agent team needs):
  list_open_tickets, get_ticket   -> tickets (+ desk)
  list_tickets (Problem 7, dashboard API only; no agent has it) -> tickets
  get_cash_position               -> cash_accounts
  list_open_invoices, get_invoice -> invoices + vendors (+ desk)
  list_payments                   -> payments
  list_vendors                    -> vendors
  project_cash_balance            -> cash_accounts (never-negative check)

Run from this folder (stdio):  python server.py
Run (HTTP):                    python server.py --http
HTTP URL:                      http://127.0.0.1:8002/mcp
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import date
from pathlib import Path

from fastmcp import FastMCP
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB_PATH = ROOT / "data" / "campus_customs_new.db"
ORIGINAL_DB_PATH = ROOT / "data" / "campus_customs.db"

mcp = FastMCP("campus-customs")


def _db_path() -> Path:
    """The working copy, or a test copy named by CAMPUS_CUSTOMS_DB. Never the original."""
    path = Path(os.environ.get("CAMPUS_CUSTOMS_DB") or DB_PATH).resolve()
    if path == ORIGINAL_DB_PATH.resolve():
        raise PermissionError("Refusing to use the original data/campus_customs.db; use the working copy.")
    return path


def _connect() -> sqlite3.Connection:
    """Open the working copy read-only so these tools can never change it."""
    db_path = _db_path()
    if not db_path.exists():
        raise FileNotFoundError(f"Working database not found: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _desk_date(conn: sqlite3.Connection) -> str:
    """The shop's 'today' from the desk table (not the real clock)."""
    return conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]


@mcp.tool
def check_stock(sku: str, size: str, qty: int = 1) -> dict:
    """Check whether an order for one SKU and size can be filled from stock.

    Returns the on-hand quantity and shelf location for the requested size,
    whether `qty` can be filled now, any shortfall, and stock in the other
    sizes of the same SKU (so the agent can offer an alternative).
    Example: check_stock("CC-TEE-WHITE", "S", 1).
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid",
            (sku,),
        ).fetchall()
    if not rows:
        return {"found": False, "sku": sku, "error": f"No inventory rows for SKU {sku!r}."}

    match = next((r for r in rows if r["size"].lower() == size.lower()), None)
    other_sizes = [
        {"size": r["size"], "qty": r["qty"], "location": r["location"]}
        for r in rows
        if match is None or r["size"] != match["size"]
    ]
    if match is None:
        return {
            "found": False,
            "sku": sku,
            "name": rows[0]["name"],
            "error": f"Size {size!r} is not stocked for {sku}.",
            "other_sizes": other_sizes,
        }
    on_hand = match["qty"]
    return {
        "found": True,
        "sku": sku,
        "name": match["name"],
        "size": match["size"],
        "requested_qty": qty,
        "on_hand": on_hand,
        "location": match["location"],
        "can_fulfill": on_hand >= qty,
        "shortfall": max(qty - on_hand, 0),
        "other_sizes": other_sizes,
    }


@mcp.tool
def get_rent_due(lease_id: int) -> dict:
    """Look up what rent is owed on a lease and when.

    Returns the space, landlord, monthly rent, next due date, and days until
    due measured from the shop's desk date (negative means overdue).
    Example: get_rent_due(1).
    """
    with _connect() as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        today = _desk_date(conn)
    if lease is None:
        return {"found": False, "lease_id": lease_id, "error": f"No lease with id {lease_id}."}

    days_until_due = (date.fromisoformat(lease["next_due"]) - date.fromisoformat(today)).days
    return {
        "found": True,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "desk_date": today,
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
        "notes": lease["notes"],
    }


@mcp.tool
def quote_bulk_order(sku: str, qty: int, discount_pct: float = 0.0) -> dict:
    """Price a bulk order for one SKU, optionally at a percentage discount.

    Returns unit cost, list price, the discounted unit price, order totals
    (revenue, cost, gross profit), margin, and whether the discounted price
    is still above unit cost. Use it to test a discount before offering one.
    Example: quote_bulk_order("CC-HOOD-NAVY", 20, 10).
    """
    if qty <= 0:
        return {"found": False, "sku": sku, "error": "qty must be positive."}
    if not 0 <= discount_pct < 100:
        return {"found": False, "sku": sku, "error": "discount_pct must be from 0 up to (not including) 100."}

    with _connect() as conn:
        price = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?",
            (sku,),
        ).fetchone()
    if price is None:
        return {"found": False, "sku": sku, "error": f"No pricing for SKU {sku!r}."}

    unit_cost = price["unit_cost"]
    list_price = price["list_price"]
    unit_price = round(list_price * (1 - discount_pct / 100), 2)
    revenue = round(unit_price * qty, 2)
    cost = round(unit_cost * qty, 2)
    profit = round(revenue - cost, 2)
    return {
        "found": True,
        "sku": sku,
        "qty": qty,
        "unit_cost": unit_cost,
        "list_price": list_price,
        "discount_pct": discount_pct,
        "unit_price": unit_price,
        "total_revenue": revenue,
        "total_cost": cost,
        "gross_profit": profit,
        "margin_pct": round(profit / revenue * 100, 1) if revenue else 0.0,
        "above_cost": unit_price > unit_cost,
    }


# --- Problem 5: facts for the agent team ------------------------------------


class Outflow(BaseModel):
    """One proposed payment to test against the cash balance."""

    label: str = Field(description="What the money is for, e.g. 'Rent lease 1'.")
    amount: float = Field(gt=0, description="Dollars leaving the account; must be positive.")


def _ticket_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _days_from_desk(conn: sqlite3.Connection, iso_date: str) -> int:
    return (date.fromisoformat(iso_date) - date.fromisoformat(_desk_date(conn))).days


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket whose status is 'open', oldest first, plus the desk date.

    Use this to see the work queue before picking a ticket to resolve.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status = 'open' ORDER BY created_at, id"
        ).fetchall()
        today = _desk_date(conn)
    return {"desk_date": today, "count": len(rows), "tickets": [_ticket_dict(r) for r in rows]}


@mcp.tool
def list_tickets(status: str | None = None) -> dict:
    """List all tickets (or only those with the given status, e.g. 'open' or
    'resolved'), oldest first, plus the desk date. Used by the dashboard API.
    """
    sql, params = "SELECT * FROM tickets", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    with _connect() as conn:
        rows = conn.execute(sql + " ORDER BY created_at, id", params).fetchall()
        today = _desk_date(conn)
    return {"desk_date": today, "count": len(rows), "tickets": [_ticket_dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket's full record (type, requester, subject, sku, size, qty,
    lease_id, invoice_id, status, notes, created_at) plus the desk date.

    Example: get_ticket(101).
    """
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        today = _desk_date(conn)
    if row is None:
        return {"found": False, "ticket_id": ticket_id, "error": f"No ticket with id {ticket_id}."}
    return {"found": True, "desk_date": today, "ticket": _ticket_dict(row)}


@mcp.tool
def get_cash_position() -> dict:
    """Get every cash account's balance and as-of date, and the total cash on hand.

    Use this before recommending any payment: cash may never go negative.
    """
    with _connect() as conn:
        rows = conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name").fetchall()
        today = _desk_date(conn)
    accounts = [{"account": r["name"], "balance": r["balance"], "as_of": r["date"]} for r in rows]
    return {
        "desk_date": today,
        "accounts": accounts,
        "total_balance": round(sum(a["balance"] for a in accounts), 2),
    }


def _invoice_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    days_until_due = _days_from_desk(conn, row["due_date"])
    return {
        "invoice_id": row["id"],
        "vendor_id": row["vendor_id"],
        "vendor_name": row["vendor_name"],
        "vendor_specialty": row["specialty"],
        "amount": row["amount"],
        "due_date": row["due_date"],
        "days_until_due": days_until_due,
        "overdue": row["status"] == "open" and days_until_due < 0,
        "status": row["status"],
        "description": row["description"],
    }


_INVOICE_SQL = """
    SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description,
           v.name AS vendor_name, v.specialty
    FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id
"""


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Get one vendor invoice with its vendor, amount, due date, status, and days
    until due from the desk date (negative = overdue).

    Example: get_invoice(501).
    """
    with _connect() as conn:
        row = conn.execute(_INVOICE_SQL + " WHERE i.id = ?", (invoice_id,)).fetchone()
        if row is None:
            return {"found": False, "invoice_id": invoice_id, "error": f"No invoice with id {invoice_id}."}
        return {"found": True, "desk_date": _desk_date(conn), "invoice": _invoice_dict(conn, row)}


@mcp.tool
def list_open_invoices() -> dict:
    """List all invoices with status 'open' (money the shop still owes vendors),
    with days until due and the total owed.
    """
    with _connect() as conn:
        rows = conn.execute(_INVOICE_SQL + " WHERE i.status = 'open' ORDER BY i.due_date, i.id").fetchall()
        invoices = [_invoice_dict(conn, r) for r in rows]
        today = _desk_date(conn)
    return {
        "desk_date": today,
        "count": len(invoices),
        "total_open": round(sum(i["amount"] for i in invoices), 2),
        "invoices": invoices,
    }


@mcp.tool
def list_payments(kind: str | None = None, ref_id: int | None = None) -> dict:
    """List payments already made, optionally filtered by kind and/or ref_id.

    Use it to check whether a rent or invoice has already been paid before
    proposing a payment. Each payment row records who approved it.
    """
    sql = "SELECT id, kind, ref_id, amount, account, paid_at, approved_by FROM payments WHERE 1=1"
    params: list = []
    if kind is not None:
        sql += " AND kind = ?"
        params.append(kind)
    if ref_id is not None:
        sql += " AND ref_id = ?"
        params.append(ref_id)
    with _connect() as conn:
        rows = conn.execute(sql + " ORDER BY paid_at, id", params).fetchall()
    payments = [dict(r) for r in rows]
    return {
        "filters": {"kind": kind, "ref_id": ref_id},
        "count": len(payments),
        "total_paid": round(sum(p["amount"] for p in payments), 2),
        "payments": payments,
    }


@mcp.tool
def list_vendors(specialty: str | None = None) -> dict:
    """List vendors with their specialty and lead time in days.

    Optional `specialty` matches part of the specialty text, case-insensitive
    (e.g. "apparel" or "mugs"). For reference only: never contact a vendor.
    """
    sql = "SELECT id, name, specialty, lead_days FROM vendors"
    params: list = []
    if specialty:
        sql += " WHERE specialty LIKE ?"
        params.append(f"%{specialty}%")
    with _connect() as conn:
        rows = conn.execute(sql + " ORDER BY id", params).fetchall()
    return {"filter": specialty, "count": len(rows), "vendors": [dict(r) for r in rows]}


@mcp.tool
def project_cash_balance(outflows: list[Outflow], account: str = "checking") -> dict:
    """Test proposed payments against a cash account, in the order given, without paying anything.

    Returns the starting balance, the running balance after each outflow, the
    ending balance, and `stays_non_negative`. If a payment would push the balance
    below zero, `first_negative` names it. Use this before recommending payments.
    Example: project_cash_balance([{"label": "Rent lease 1", "amount": 2400}]).
    """
    with _connect() as conn:
        row = conn.execute("SELECT name, balance, date FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if row is None:
        return {"found": False, "account": account, "error": f"No cash account named {account!r}."}

    balance = row["balance"]
    steps = []
    first_negative = None
    for item in outflows:
        balance = round(balance - item.amount, 2)
        steps.append({"label": item.label, "amount": item.amount, "balance_after": balance})
        if balance < 0 and first_negative is None:
            first_negative = item.label
    return {
        "found": True,
        "account": row["name"],
        "starting_balance": row["balance"],
        "as_of": row["date"],
        "total_outflows": round(sum(i.amount for i in outflows), 2),
        "steps": steps,
        "ending_balance": balance,
        "stays_non_negative": first_negative is None,
        "first_negative": first_negative,
        "note": "Projection only. No payment was made; every payment needs human approval.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Campus Customs MCP server")
    parser.add_argument("--http", action="store_true", help="serve over HTTP instead of stdio")
    args = parser.parse_args()
    if args.http:
        mcp.run(transport="http", host="127.0.0.1", port=8002)
    else:
        mcp.run()
