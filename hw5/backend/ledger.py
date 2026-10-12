"""The only code that writes to the working database.

Called only by the human-approval, human-resolution, and reset routes in main.py. No agent has a
tool that reaches this module, and the MCP server stays read-only. Every write
targets the working copy; the original data/campus_customs.db is only ever read
(as the source for a reset).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

HW5_DIR = Path(__file__).resolve().parents[1]
ORIGINAL_DB = (HW5_DIR / "data" / "campus_customs.db").resolve()
DEFAULT_WORKING_DB = HW5_DIR / "data" / "campus_customs_new.db"


class LedgerError(Exception):
    """A rule stopped the write. `status` is the HTTP status the API should return."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def working_db() -> Path:
    """Same rule as the MCP server: the working copy (or a test copy), never the original."""
    path = Path(os.environ.get("CAMPUS_CUSTOMS_DB") or DEFAULT_WORKING_DB).resolve()
    if path == ORIGINAL_DB:
        raise PermissionError("Refusing to write to the original data/campus_customs.db.")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class PaymentResult:
    payment_id: int
    kind: str
    ref_id: int | None
    amount: float
    balance_before: float
    balance_after: float
    paid_at: str
    ticket_status: str


def execute_approved_payment(
    *,
    kind: str,
    ref_id: int | None,
    amount: float,
    approved_by: str,
    ticket_id: int,
    resolve_ticket: bool,
    account: str = "checking",
) -> PaymentResult:
    """Record one human-approved payment or purchase in a single transaction.

    Re-checks every rule inside the transaction (the API validated them already,
    but the database is the final authority): the account exists, the balance
    covers the amount, an invoice is still open and matches, and rent for that
    lease hasn't already been paid. Anything wrong rolls back with no change.
    """
    if kind not in ("invoice", "rent", "purchase"):
        raise LedgerError(422, f"Unknown payment kind {kind!r}.")
    if not amount > 0:
        raise LedgerError(422, "Amount must be positive.")

    conn = sqlite3.connect(working_db(), isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")  # take the write lock before reading the balance
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            raise LedgerError(409, f"No cash account named {account!r}.")
        before = acct["balance"]
        if before - amount < 0:
            raise LedgerError(409, f"Insufficient cash: {account} has ${before:,.2f}; ${amount:,.2f} would leave ${before - amount:,.2f}.")

        if kind == "invoice":
            inv = conn.execute("SELECT amount, status FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if inv is None:
                raise LedgerError(404, f"Invoice {ref_id} not found.")
            if inv["status"] != "open":
                raise LedgerError(409, f"Invoice {ref_id} is already {inv['status']}.")
            if abs(inv["amount"] - amount) > 0.005:
                raise LedgerError(409, f"Invoice {ref_id} is ${inv['amount']:,.2f}, not ${amount:,.2f}.")
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
        elif kind == "rent":
            paid = conn.execute("SELECT id FROM payments WHERE kind = 'rent' AND ref_id = ?", (ref_id,)).fetchone()
            if paid is not None:
                raise LedgerError(409, f"Rent for lease {ref_id} is already paid (payment {paid['id']}).")

        today = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()["date_today"]
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, amount, account, today, approved_by),
        )
        updated = conn.execute(
            "UPDATE cash_accounts SET balance = ROUND(balance - ?, 2), date = ? WHERE name = ? AND balance - ? >= 0",
            (amount, today, account, amount),
        )
        if updated.rowcount != 1:  # belt and braces: the WHERE clause also refuses a negative balance
            raise LedgerError(409, "Cash would go negative; nothing was recorded.")
        if resolve_ticket:
            conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ?", (ticket_id,))
        after = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()["balance"]
        status = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()["status"]
        conn.execute("COMMIT")
        return PaymentResult(cur.lastrowid, kind, ref_id, amount, before, after, today, status)
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def resolve_ticket(ticket_id: int) -> str:
    """Mark one open ticket resolved after a human approves its proposed resolution.

    Moves no money: only `tickets.status` changes. Refuses a ticket that is
    missing or not open, so a resolution can't be recorded twice.
    """
    conn = sqlite3.connect(working_db(), isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise LedgerError(404, f"Ticket {ticket_id} not found.")
        if row[0] != "open":
            raise LedgerError(409, f"Ticket {ticket_id} is already {row[0]}.")
        conn.execute("UPDATE tickets SET status = 'resolved' WHERE id = ? AND status = 'open'", (ticket_id,))
        conn.execute("COMMIT")
        return "resolved"
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def reset_working_db() -> str:
    """Replace the working copy with a fresh byte-for-byte copy of the original.

    The original is only read. The copy goes to a temp file next to the working
    DB, then atomically replaces it. Returns the new working DB's SHA-256.
    """
    target = working_db()
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".reset-", suffix=".db")
    os.close(fd)
    shutil.copyfile(ORIGINAL_DB, tmp)
    os.replace(tmp, target)
    digest = _sha256(target)
    if digest != _sha256(ORIGINAL_DB):
        raise RuntimeError("Reset copy does not match the original database.")
    return digest
