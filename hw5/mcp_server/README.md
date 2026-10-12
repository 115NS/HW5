# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server (`campus-customs`) that gives the Homework 5 agents (Boss, Inventory, Accounting, Facilities, Customer Service) read-only access to the shop's data. It is the agents' only source of shop facts.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy at the Homework-5 root. The path is resolved relative to `server.py`, so the server works from any directory.
- **Read-only:** the database is opened in SQLite read-only mode (`mode=ro`), so no tool can change data.
- **Never touched:** the original `data/campus_customs.db`.
- **Test copies:** `CAMPUS_CUSTOMS_DB` can point the server at a test copy; it refuses the original file.
- **Dates:** "today" comes from the `desk` table (`2026-08-31`), not the real clock.
- **No outside effects:** no tool pays, orders, sends, or contacts anyone.

## Tools (12)

### Problem 3 (behaviour unchanged since Problem 3)

| Tool | Reads | Ticket | Returns |
|---|---|---|---|
| `check_stock(sku, size, qty=1)` | `inventory` | #101 (`CC-TEE-WHITE` S) and #103 (`CC-HOOD-NAVY` M) | on-hand qty, location, `can_fulfill`, `shortfall`, stock in the SKU's other sizes |
| `get_rent_due(lease_id)` | `leases` (+ `desk`) | #102 (lease 1); used by Facilities and, since Problem 9, Accounting | space, landlord, `monthly_rent`, `next_due`, `days_until_due`, `overdue` |
| `quote_bulk_order(sku, qty, discount_pct=0)` | `pricing` | #103 (20× `CC-HOOD-NAVY`) | unit cost, list and discounted unit price, revenue, cost, gross profit, margin %, `above_cost` |

### Problem 5 (facts the agent team needs)

| Tool | Reads | Used by | Returns |
|---|---|---|---|
| `list_open_tickets()` | `tickets` (+ `desk`) | Boss | every `open` ticket, oldest first |
| `get_ticket(ticket_id)` | `tickets` (+ `desk`) | Boss, Customer Service | the full ticket record |
| `get_cash_position()` | `cash_accounts` (+ `desk`) | Accounting | each account's balance and as-of date, total |
| `get_invoice(invoice_id)` | `invoices`, `vendors` (+ `desk`) | Accounting | amount, vendor, due date, `days_until_due`, `overdue`, status |
| `list_open_invoices()` | `invoices`, `vendors` (+ `desk`) | Accounting | all open invoices and the total owed |
| `list_payments(kind=None, ref_id=None)` | `payments` | Accounting, Facilities | payments already made (including `approved_by`) |
| `list_vendors(specialty=None)` | `vendors` | Inventory | name, specialty, `lead_days` (reference only; never contact) |
| `project_cash_balance(outflows, account="checking")` | `cash_accounts` | Accounting, code guardrails | running and ending balance for proposed payments, `stays_non_negative`, `first_negative`. A projection only; it pays nothing. Amounts must be positive. |

### Problem 7 (dashboard API only)

| Tool | Reads | Used by | Returns |
|---|---|---|---|
| `list_tickets(status=None)` | `tickets` (+ `desk`) | `backend/main.py` (`GET /api/tickets`); no agent has it | every ticket (or one status, e.g. `resolved`), oldest first |

Error handling:
- An unknown SKU, size, ticket, lease, invoice, or account returns `{"found": false, "error": ...}` instead of raising, so an agent can recover.
- `quote_bulk_order` rejects a non-positive `qty` and discounts outside 0–<100%.

## Setup and running

From `Homework/Homework-5`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r mcp_server/requirements.txt
```

```bash
python mcp_server/server.py          # stdio
python mcp_server/server.py --http   # http://127.0.0.1:8002/mcp
```

## Who connects to it

- **Claude Code:** via `.mcp.json` (Problem 4). The smoke tests are in `output/mcp_smoke.json`.
- **The dashboard API:** `backend/main.py` calls this server in-process for every read (tickets, cash, invoices, rent, cash projections).
- **The agent team:** `backend/agents.py` starts this server over stdio with the same interpreter and gives each agent only its own tools.

To run the tests:

```bash
python -m pytest -q tests/test_mcp_tools.py
```
