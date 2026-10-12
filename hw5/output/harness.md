# Campus Customs Multi-Agent Harness

Working notes for the Homework 5 multi-agent operations system (Boss, Inventory, Accounting, Facilities, Customer Service). Later problems add sections below.

## Database

- **Original (read-only):** `data/campus_customs.db`. Never write to it.
- **Working copy:** `data/campus_customs_new.db`. All agents and tools use this copy.
- At the time of copying, both files had the same SHA-256 (`23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a`). The copy passed `PRAGMA integrity_check` and `PRAGMA foreign_key_check`, row counts matched for all 9 tables, and a write test (rolled back) succeeded.
- The database has 9 tables and no views, triggers, or extra indexes.
- SQLite does not enforce foreign keys unless `PRAGMA foreign_keys = ON` is set per connection.

### Tables

Schema taken from `sqlite_master`. Row counts are as of the copy.

#### `desk` (1 row)
| Field | Type |
|---|---|
| `date_today` | TEXT NOT NULL |
| `notes` | TEXT |

Why it matters: it holds the shop's "today" (`2026-08-31`), so every agent judges due dates, lateness, and lead times against the same date instead of the real clock.

#### `inventory` (10 rows)
| Field | Type |
|---|---|
| `sku` | TEXT NOT NULL, part of PK |
| `name` | TEXT NOT NULL |
| `size` | TEXT NOT NULL, part of PK |
| `qty` | INTEGER NOT NULL |
| `location` | TEXT NOT NULL |

Primary key is `(sku, size)`. Why it matters: the Inventory agent uses it to check whether a ticket can be filled from stock and where the item sits.

#### `pricing` (4 rows)
| Field | Type |
|---|---|
| `sku` | TEXT PRIMARY KEY |
| `unit_cost` | REAL NOT NULL |
| `list_price` | REAL NOT NULL |

Why it matters: it gives the cost and list price that Accounting and Customer Service need to quote orders and judge whether a discount still leaves a margin.

#### `vendors` (3 rows)
| Field | Type |
|---|---|
| `id` | INTEGER PRIMARY KEY |
| `name` | TEXT NOT NULL |
| `specialty` | TEXT NOT NULL |
| `lead_days` | INTEGER NOT NULL |

Why it matters: Inventory uses it to pick a supplier for restocks and estimate arrival dates from `lead_days`; agents must never actually contact these vendors.

#### `leases` (1 row)
| Field | Type |
|---|---|
| `id` | INTEGER PRIMARY KEY |
| `space_name` | TEXT NOT NULL |
| `landlord` | TEXT NOT NULL |
| `monthly_rent` | REAL NOT NULL |
| `next_due` | TEXT NOT NULL |
| `notes` | TEXT |

Why it matters: Facilities uses it to confirm rent amounts and due dates before passing a rent payment to Accounting.

#### `cash_accounts` (1 row)
| Field | Type |
|---|---|
| `name` | TEXT PRIMARY KEY |
| `balance` | REAL NOT NULL |
| `date` | TEXT NOT NULL |

Why it matters: Accounting checks it before any payment, because the balance can never go negative.

#### `payments` (0 rows)
| Field | Type |
|---|---|
| `id` | INTEGER PRIMARY KEY |
| `kind` | TEXT NOT NULL |
| `ref_id` | INTEGER |
| `amount` | REAL NOT NULL |
| `account` | TEXT NOT NULL |
| `paid_at` | TEXT NOT NULL |
| `approved_by` | TEXT NOT NULL |

Why it matters: it is the audit trail of money leaving the shop, and `approved_by` (required) records the human approval every payment needs.

#### `invoices` (1 row)
| Field | Type |
|---|---|
| `id` | INTEGER PRIMARY KEY |
| `vendor_id` | INTEGER NOT NULL, FK → `vendors.id` |
| `amount` | REAL NOT NULL |
| `due_date` | TEXT NOT NULL |
| `status` | TEXT NOT NULL |
| `description` | TEXT |

Why it matters: Accounting uses it to see what the shop owes vendors and whether anything is overdue.

#### `tickets` (3 rows)
| Field | Type |
|---|---|
| `id` | INTEGER PRIMARY KEY |
| `type` | TEXT NOT NULL |
| `requester` | TEXT NOT NULL |
| `subject` | TEXT NOT NULL |
| `sku` | TEXT |
| `size` | TEXT |
| `qty` | INTEGER |
| `lease_id` | INTEGER, FK → `leases.id` |
| `invoice_id` | INTEGER, FK → `invoices.id` |
| `status` | TEXT NOT NULL |
| `notes` | TEXT |
| `created_at` | TEXT NOT NULL |

Why it matters: this is the work queue; the Boss reads each ticket's `type` and linked fields to decide which agents to delegate to.

### How the tables relate

Declared foreign keys:
- `tickets.invoice_id` → `invoices.id`
- `tickets.lease_id` → `leases.id`
- `invoices.vendor_id` → `vendors.id`

Implied links (matching columns, no declared FK):
- `tickets.(sku, size)` → `inventory.(sku, size)`
- `tickets.sku` → `pricing.sku` (also `inventory.sku` → `pricing.sku`)
- `payments.account` → `cash_accounts.name`
- `payments.(kind, ref_id)` → probably an invoice or lease id, depending on `kind`. The table is empty, so the allowed `kind` values aren't shown in the data.

```
tickets ──invoice_id──▶ invoices ──vendor_id──▶ vendors
   │  └──lease_id────▶ leases
   └──(sku, size)───▶ inventory ──sku──▶ pricing
payments ──account──▶ cash_accounts
payments ──(kind, ref_id)──▶ invoices / leases
desk = shared "today" for every date comparison
```

### The three open tickets

Today on the desk is **2026-08-31**. Checking has **$3,400.00** (dated 2026-08-31).

**#101 · `customer_order` · Tauhid Zaman · "Bulldog tee"**
- Wants `CC-TEE-WHITE`, size S, qty 1.
- Inventory: S has 0 in stock (Aisle B). Other sizes: M 5, L 3, XL 2.
- Pricing: $8.00 cost, $28.00 list.
- Linked to `invoice_id` 501: Bulldog Print Co (apparel reprint, 5 lead days), $840.00, "Rush reprint CC-TEE-WHITE S", due 2026-08-28, status `open`. That is 3 days overdue.
- So the order depends on a reprint from a vendor whose invoice is still unpaid.
- Tables: tickets, inventory, pricing, invoices, vendors, cash_accounts, desk.

**#102 · `rent_notice` · Elm City Properties · "Rent due"**
- Note: "Email: shop rent due in 2 days."
- Linked to `lease_id` 1: Chapel Street shop, landlord Elm City Properties, $2,400.00/month, next due 2026-09-02. That is 2 days after desk date, which matches the note.
- Tables: tickets, leases, cash_accounts, payments, desk.

**#103 · `price_override` · Yale AI Club · "Bulk hoodie discount"**
- Wants `CC-HOOD-NAVY`, size M, qty 20, at a bulk discount.
- Inventory: M has 8 in stock (Aisle A), so it is 12 short. All sizes total 32 (S 4, M 8, L 14, XL 6).
- Pricing: $22.00 cost, $58.00 list. At list price, 20 hoodies = $1,160.00 revenue on $440.00 cost.
- Bulldog Print Co (apparel reprint, 5 lead days) is the apparel vendor in the table.
- Tables: tickets, inventory, pricing, vendors, desk.

### Constraints the data already shows

- **Cash.** Paying both the rent ($2,400) and invoice 501 ($840) totals $3,240. That would leave $160 out of $3,400, so the order and timing of payments matter. Any reprint or restock spending comes out of the same account.
- **Human approval.** `payments.approved_by` is NOT NULL, and the `payments` table is empty, so no payment has been approved yet.
- **No outside contact.** Requesters, the landlord, and vendors are real-world-style contacts. Agents must not message any of them; they may only draft replies.

## MCP server (Problem 3)

- **Code:** `mcp_server/server.py` (FastMCP, server name `campus-customs`).
- **Docs:** `mcp_server/README.md`.
- **Database:** opens `data/campus_customs_new.db` read-only and never opens the original.
- **Tests:** each tool was called in memory against the real data (results below).

| Tool | Table read | Ticket | Why this tool fits the ticket |
|---|---|---|---|
| `check_stock(sku, size, qty)` | `inventory` | #101 `customer_order`: Tauhid Zaman wants 1× `CC-TEE-WHITE` size S | Ticket #101 depends on whether row (`CC-TEE-WHITE`, `S`) can cover qty 1. The tool returns `on_hand = 0`, `can_fulfill = false`, `shortfall = 1`, and the in-stock M/L/XL sizes, which tells the agents to either wait on the reprint behind invoice 501 or offer another size. |
| `get_rent_due(lease_id)` | `leases` (+ `desk` for today's date) | #102 `rent_notice`: Elm City Properties says rent is due in 2 days, `lease_id = 1` | Ticket #102 only names a lease, so the tool reads lease 1 and returns the actual amount ($2,400.00), due date (2026-09-02), and `days_until_due = 2`. That confirms the landlord's email matches our records before anyone pays. |
| `quote_bulk_order(sku, qty, discount_pct)` | `pricing` | #103 `price_override`: Yale AI Club wants 20× `CC-HOOD-NAVY` at a bulk discount | Ticket #103 asks for a discount, so the tool takes the hoodie's $22.00 cost and $58.00 list price and calculates revenue, profit, margin, and `above_cost` for any discount. A discount can be tested before anyone offers it (e.g. 0% → $1,160 revenue, $720 profit; 10% → $1,044, $604). |

`check_stock("CC-HOOD-NAVY", "M", 20)` also covers the stock side of #103 (8 on hand, 12 short).

These three tools don't cover cash, invoice 501, or human approval; Problem 5 adds those (see that section). Ticket status is still never written.

## Claude Code connection (Problem 4)

Server entry `campus-customs` (stdio, no env vars, no secrets) appears in two files:

- **`Homework/Homework-5/.mcp.json`:** the Homework 5 project config. Claude Code loads it when started in `Homework-5`.
- **`AI Foundations/.mcp.json`:** merged next to `yale-som-courses`. Claude Code loads it when started in the course root, which is where this course's sessions run.

```json
"campus-customs": {
  "type": "stdio",
  "command": ".venv/bin/python",
  "args": ["mcp_server/server.py"]
}
```

- **Launch check:** the exact `command` and `args` were started over stdio with a FastMCP client. The handshake succeeded and listed `check_stock`, `get_rent_due`, `quote_bulk_order`.
- **Not connected yet:** Claude Code reads `.mcp.json` only when a session starts. The server becomes available after a new session is opened and the user approves `campus-customs`.

### Smoke tests through Claude Code

**Status: complete (2026-10-11), 3/3 pass.** The tests ran in a new Code-tab session started in `AI Foundations`, launched from a Claude-drafted task chip. That session's connector status showed `campus-customs · project · stdio · connected · 3 tools`. Each tool was called once through MCP, and each output was checked against `data/campus_customs_new.db` with `sqlite3 -readonly`. Full outputs and SQL are in `output/mcp_smoke.json`.

| Ticket | Tool | Arguments | Result | DB check |
|---|---|---|---|---|
| #101 | `mcp__campus-customs__check_stock` | `CC-TEE-WHITE`, `S`, qty 1 | 0 on hand in Aisle B, can't fill, shortfall 1. Other sizes: M 5, L 3, XL 2 | ✅ `inventory` rows match |
| #102 | `mcp__campus-customs__get_rent_due` | lease 1 | Chapel Street shop, Elm City Properties, $2,400 due 2026-09-02, 2 days after desk date 2026-08-31, not overdue | ✅ `leases` id 1 + `desk` match |
| #103 | `mcp__campus-customs__quote_bulk_order` | `CC-HOOD-NAVY`, qty 20, 0% | $58 × 20 = $1,160 revenue, $440 cost, $720 gross profit, 62.1% margin, above cost | ✅ `pricing` (22 / 58) matches |

Original `data/campus_customs.db` sha256 was unchanged after the tests: `23686a90…f360a`.

### Troubleshooting timeline (2026-10-11)

1. **Issue:** in the original Code-tab session, `campus-customs` did not appear in the connector list, and none of its three tools were available. Several "continue" attempts got the same result.
2. **Diagnosis:** that session's Claude Code process started at 16:01, but `campus-customs` was added to `.mcp.json` at 17:04. Claude Code reads project MCP servers only when a session starts, so this session never loaded the new server.
3. **Diagnostic checks** (none of these were smoke tests):
   - Both `.mcp.json` files are valid JSON with no secrets.
   - The absolute paths to the HW5 `.venv/bin/python` interpreter and `mcp_server/server.py` exist, and the interpreter is executable.
   - A manual stdio startup completed the MCP handshake (`initialize` and `tools/list` returned all three tools).
   - Claude Code's own `claude mcp list` / `claude mcp get campus-customs` found the server from the root `.mcp.json`, and `~/.claude.json` does not disable it.
4. **Intermediate attempt (partial):** a separate Claude Code process launched from the terminal (`claude -p --strict-mcp-config --mcp-config .mcp.json`) reported `campus-customs: connected` and exposed all three tools. It could not call them, because it returned `Not logged in` (desktop sessions get their authentication from the app, and a terminal-launched process doesn't receive it). **No smoke tests ran in this process.**
5. **Resolution:** a separate, newly started Code-tab session named `Finish HW5 Problem 4 MCP smoke tests` showed `campus-customs` as connected with 3 tools. It called `check_stock`, `get_rent_due` and `quote_bulk_order` once each through MCP. Each output was checked against `data/campus_customs_new.db` with read-only SQL (`sqlite3 -readonly`).
6. **Final status:** all three tests passed (3/3). `output/mcp_smoke.json` was created, and **Problem 4 is complete**. The original `data/campus_customs.db` was not modified (sha256 unchanged).

The details below are the evidence gathered during steps 2–4.

### Connection diagnosis (2026-10-11)

| Layer | Check | Result |
|---|---|---|
| Server | Raw JSON-RPC over stdio, started from `AI Foundations` (the directory Claude Code launches from) | ✅ `initialize` → `campus-customs` 4.1.0. `tools/list` → `check_stock`, `get_rent_due`, `quote_bulk_order`. stdout is pure JSON-RPC (the FastMCP banner goes to stderr). No errors. |
| Config | Both `.mcp.json` files | ✅ Valid JSON. The `command` (HW5 `.venv/bin/python`) exists and is executable, and the script path exists. Paths are absolute, so the working directory doesn't matter. No secrets. |
| Approval | `~/.claude.json` project entry for `AI Foundations` | ✅ `campus-customs` is not in `disabledMcpjsonServers`. |
| Claude Code | Running session process | ❌ The Code-tab session (`claude` pid 45926) started at **16:01**, but `.mcp.json` got `campus-customs` at **17:04**. No newer Claude Code session exists for this folder; every "continue" message reached the same process. Project MCP servers are read only at process start, so this process never discovered the server. |

### Claude Code's own checks (bundled CLI 2.1.288)

The desktop app bundles the Claude Code CLI at `~/Library/Application Support/Claude/claude-code/2.1.288/<id>/claude.app/Contents/MacOS/claude`; it is not on `PATH`.

- **`claude mcp list`, `claude mcp get campus-customs`** (run in `AI Foundations`): Claude Code **discovers** `campus-customs` from the root `.mcp.json` as project scope, with the exact interpreter and script paths. The CLI shows it as `⏸ Pending approval`. `yale-som-courses` shows the same CLI status but is connected in the desktop session, so the desktop app tracks project-server approval itself.
- **Fresh Claude Code process:** `claude -p … --strict-mcp-config --mcp-config .mcp.json --tools "" --output-format stream-json` (run in `Homework-5`). The `init` event reported `campus-customs: connected` and exposed `mcp__campus-customs__check_stock`, `mcp__campus-customs__get_rent_due`, `mcp__campus-customs__quote_bulk_order`. **The server works inside Claude Code.**
- **Same process can't call the tools:** it returned `Not logged in`. Desktop Code-tab sessions are authenticated by the app (`CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH`), and no credential is passed to child processes, so a headless CLI can see the tools but cannot run a model turn to call them.

**Root cause, confirmed:** the Code-tab process that receives these messages (pid 45926) started at 16:01 and had already built its MCP list. A running Code-tab session can't add a project `.mcp.json` server: the session tools only enable claude.ai connectors or reconnect servers it already knows, and neither applies here. The tools can only be invoked from a Code-tab session started after 17:04.

**Conclusion:** the server and config are correct. The server isn't loaded because the Code-tab session was started before the config change and was never replaced by a new one.

**Fix:**
1. Start a brand-new Code-tab session in `AI Foundations`.
2. Approve `campus-customs`.
3. Verify the session's MCP/connector list shows `campus-customs · connected · 3 tools`.

Results go in `output/mcp_smoke.json`.

## Multi-agent system (Problem 5)

Five PydanticAI agents work one ticket at a time. Each agent:
- runs on **`gpt-6-luna` via Portkey** (`https://api.portkey.ai/v1`, Responses API, `PORTKEY_API_KEY` from the environment or the AI Foundations `.env`; reasoning effort low),
- gets every shop fact from the **`campus-customs` MCP server**, which reads `data/campus_customs_new.db` read-only,
- returns structured output and never executes anything.

There is no separate shop-tools layer. The agents' only data path is MCP, and the code-level guardrails use the same MCP server.

### Code layout

| Path | What it is |
|---|---|
| `backend/models.py` | Data types: `Fact`, `ProposedAction`, `SpecialistReport`, `CustomerReplyDraft`, `BossProposal`, `RuleCheck`, `TicketResolution` |
| `backend/prompts/{boss,inventory,accounting,facilities,customer_service}.md` | One prompt per agent: role, responsibilities, MCP tools, delegation boundaries, shop rules, output |
| `backend/agents.py` | `Team`: builds the 5 agents, one shared MCP stdio connection, per-agent tool filters, delegation tools, loop limits, audit logging |
| `backend/guardrails.py` | Code-level shop-rule checks applied to every Boss proposal |
| `backend/audit.py` | Append-only, hash-chained audit trail (`output/audit_trail.json`) |
| `backend/run_tickets.py` | CLI for live runs (`python -m backend.run_tickets --ticket 101` / `--all`) |
| `tests/` | 37 offline tests: real MCP server, scripted models, no Portkey |

### Agents, responsibilities, and delegation boundaries

| Agent | Responsibility | MCP tools it may call | May delegate to | Output |
|---|---|---|---|---|
| **Boss** | Reads the ticket, picks the specialists, gives each one a precise task, consolidates the findings into options, a recommendation, and proposed actions | `get_ticket`, `list_open_tickets` | Inventory, Accounting, Facilities, Customer Service | `BossProposal` → guardrails → `TicketResolution` |
| **Inventory** | Stock on hand, shortfalls, in-stock alternatives, vendor and lead time for restocks | `check_stock`, `list_vendors` | none (leaf) | `SpecialistReport` |
| **Accounting** | Cash position, invoices, payments already made, cash projections, pricing, discounts, margins | `get_cash_position`, `list_open_invoices`, `get_invoice`, `list_payments`, `project_cash_balance`, `quote_bulk_order` | none (leaf) | `SpecialistReport` |
| **Facilities** | Leases, rent amount and due date, whether rent is already paid, space and maintenance issues | `get_rent_due`, `list_payments` | Accounting (cash check before recommending rent) | `SpecialistReport` |
| **Customer Service** | Interprets the requester's ask, builds honest customer-facing options, drafts a reply that is never sent | `get_ticket` | Inventory, Accounting | `SpecialistReport` (draft reply inside) |

The boundaries are enforced in code (`backend/agents.py`), not just in the prompts:
- **Tool scope:** each agent's MCP toolset is `.filtered()` to its own tools. A test confirms no agent ever called a tool outside its list.
- **Who can delegate:** an agent only has `delegate_to_<x>` tools for the targets in `DELEGATES`. Specialists report back to whoever called them, and only the Boss produces a resolution. The graph has no cycles.
- **No loops:**
  - A delegation to an agent already in the chain is refused.
  - The chain can be at most 3 deep (Boss → specialist → specialist).
  - Each ticket gets at most 8 delegations.
  - A repeated identical request returns the earlier answer instead of running the specialist again (`delegation_reused`).
  - One `UsageLimits(request_limit=40, tool_calls_limit=60)` budget is shared by every run for a ticket.
- **Failures:** if a specialist errors, the caller gets `{"error": ...}` and the run continues. The failure is logged as `error` + `delegation_failed`.
- **No approval power:** specialists can't approve anything. `ProposedAction.status` can only be `proposed` or `blocked_by_guardrail`, and consequential kinds (payment, restock order, discount, substitute offer, customer reply) are forced to `requires_human_approval = true`.

### MCP tools and database tables (11 tools, all read-only)

| Tool | Tables | Used by | Added in |
|---|---|---|---|
| `check_stock(sku, size, qty)` | `inventory` | Inventory | P3 |
| `get_rent_due(lease_id)` | `leases`, `desk` | Facilities | P3 |
| `quote_bulk_order(sku, qty, discount_pct)` | `pricing` | Accounting | P3 |
| `list_open_tickets()` | `tickets`, `desk` | Boss | P5 |
| `get_ticket(ticket_id)` | `tickets`, `desk` | Boss, Customer Service | P5 |
| `get_cash_position()` | `cash_accounts`, `desk` | Accounting | P5 |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | Accounting | P5 |
| `list_open_invoices()` | `invoices`, `vendors`, `desk` | Accounting | P5 |
| `list_payments(kind, ref_id)` | `payments` | Accounting, Facilities | P5 |
| `list_vendors(specialty)` | `vendors` | Inventory | P5 |
| `project_cash_balance(outflows, account)` | `cash_accounts` | Accounting, guardrails | P5 |

- **Problem 3 tools unchanged:** a baseline of 11 Problem 3 calls (`tests/baseline_problem3_tools.json`, captured before any edit) still returns identical output, so `output/mcp_smoke.json` remains valid.
- **Why each new tool exists:**
  - Tickets: the Boss must read the actual ticket record.
  - Cash, invoices, payments: Accounting needs them for #101's invoice 501 and #102's cash check.
  - Vendors: Inventory needs lead times for restocks.
  - `project_cash_balance`: Accounting and the guardrails need it to test the never-negative rule.
- **No write tools:** there are no write, pay, order, or send tools.

### The open tickets and how the team handles them

All values come from MCP at run time. These are the database values as of the copy (desk date 2026-08-31, checking $3,400.00).

| Ticket | Record | Expected routing | Facts the team should find |
|---|---|---|---|
| **#101** `customer_order`, Tauhid Zaman | 1× `CC-TEE-WHITE` S, `invoice_id` 501 | Boss → Customer Service (→ Inventory), Boss → Accounting (invoice 501) | S: 0 on hand (M 5, L 3, XL 2). Invoice 501: $840 open, due 2026-08-28, 3 days overdue (Bulldog Print Co, 5 lead days). Options: another size, wait for the reprint, and whether the overdue invoice holds it up. Draft reply only. |
| **#102** `rent_notice`, Elm City Properties | `lease_id` 1 | Boss → Facilities (→ Accounting) | $2,400 due 2026-09-02 (2 days); no rent payment on record; rent + open invoice 501 → $160 left, never negative. A rent **payment proposal** pending human approval; nothing paid. |
| **#103** `price_override`, Yale AI Club | 20× `CC-HOOD-NAVY` M, discount requested | Boss → Customer Service (→ Inventory, → Accounting) | M: 8 on hand, 12 short (S 4, L 14, XL 6). At list $1,160 revenue / $720 profit (62.1%); 10% off $1,044 / $604 (57.9%); unit cost $22. Options: partial fill, restock, other sizes, a discount within margin. No order placed; draft reply only. |

The offline tests check exactly these values against the database. The live run's actual outcomes, including where they fell short of this table (#102 had no rent payment proposal, #103 had no vendor lead time), are under **Live run** below.

### Safety guardrails

| Rule | Prompt | Schema | Code check |
|---|---|---|---|
| Payments require human approval | Every prompt | `requires_human_approval` forced true for consequential kinds; `status` can't be "executed"/"approved" | `apply_guardrails` checks every consequential action; `approval_status = pending_human_approval` |
| Cash never negative | Accounting, Facilities, Boss | - | Every payment / restock outflow (plus earlier proposals in the same batch) is projected through MCP `project_cash_balance`; any outflow that would go below $0, or has no amount, is `blocked_by_guardrail` |
| No contact with customers or vendors | Every prompt | `CustomerReplyDraft.sent` is `Literal[False]` | No send, email, or order tools exist anywhere; the rule check records it |
| No real payments or orders, no DB changes | Every prompt | - | MCP opens the DB with `mode=ro` (a test proves a write fails). Every test asserts both DB files' SHA-256 are unchanged. The original DB is never opened by the server |
| No invented facts | Every prompt ("cite the source") | `Fact.source` required | Specialist reports are cached and passed verbatim; ticket id mismatches are corrected and flagged |
| No secrets | - | - | The key is read from the environment and never logged; the audit trail stores no headers or keys |

### Audit trail (`output/audit_trail.json`)

One JSON array, append-only. Each entry has:
- `seq`, `ts`, `run_id`, `ticket_id`, `agent`, `action`, `chain` (delegation path)
- optionally `step`, `tool` (`name`, `args`, `result`), `delegation` (`from`, `to`, `task`), `error`, `approval_status`, `details`
- `prev_hash` + `hash` (SHA-256 chain)

`AuditTrail.verify()` detects any edit or deletion, and appends are refused if the chain is broken.

Actions recorded:
- **Run boundaries:** `run_start` (models, DB, limits), `run_end` (status, delegations, requests, tokens)
- **Agent loop:** `agent_start` (prompt, tools, allowed delegates), `model_step` (calls the model requested), `tool_call` / `tool_result` (every MCP call), `agent_output`
- **Delegation:** `delegation_request` / `delegation_result`, `delegation_reused`, `delegation_blocked`, `delegation_failed`
- **Errors and rules:** `error`, `guardrail_check`, `resolution` (with `approval_status`)

Before the live run the file was `[]`. It now holds the 200 entries from the single live run below and nothing else. The tests write their own trails to temporary folders, so scripted runs never mix with real ones. A run's `run_start.details.models` shows whether it was live (`gpt-6-luna`) or scripted.

### Tests (offline, no Portkey)

`python -m pytest -q` from `Homework-5`: **37 passed**.

- **`test_mcp_tools.py`:** Problem 3 tools unchanged (11 baseline cases); new tools equal direct read-only SQL; the server connection can't write.
- **`test_guardrails.py`:** affordable payment → pending approval; overdraft → blocked; earlier batch proposals count; missing amount → blocked; wrong ticket id flagged; schema forbids "executed" and `sent=true`.
- **`test_audit.py`:** hash chain; edits and deletions detected; appends refused after tampering.
- **`test_team.py`:** the full team on #101–#103 over **real MCP stdio**, with PydanticAI `FunctionModel` scripts standing in for gpt-6-luna. It checks:
  - the expected delegation paths;
  - every fact against the database;
  - each agent's tool scope;
  - audit completeness and chain;
  - repeat-delegation reuse, the delegation limit, and specialist-failure handling.

  The scripts contain no shop values; every number comes from MCP.

### Live run (2026-10-11, 18:44–18:45 EDT)

**Pre-run safety review (all passed before any model call):**
- `output/audit_trail.json` was `[]`, and `output/proposed_resolutions.json` did not exist.
- Both DB SHA-256s were `23686a90…f360a`.
- `MODEL_NAME = "gpt-6-luna"`, Portkey base URL, key read from the environment only.
- Every SQL statement in the server is a `SELECT` (11 literals, 0 commits), opened `mode=ro`.
- No send, HTTP, email, payment, or order code exists in `backend/` or `mcp_server/`, and all 11 MCP tools are read-only.
- The backend writes only the audit trail (append after chain verification) and `proposed_resolutions.json`.

Change before the run:
- `run_tickets.py` now records a failing ticket and continues, so one failure can't force a rerun of the others. Tests were re-run: 37 passed.

**Command (run once):**

```bash
python -m backend.run_tickets --ticket 101 --ticket 102 --ticket 103
```

Exit 0. Proposals are in `output/proposed_resolutions.json`, and 200 entries were appended to `output/audit_trail.json` (chain intact).

**Portkey usage:**
- **45 model requests**, all `gpt-6-luna`. PydanticAI's request counter matches the 45 `model_step` audit entries.
- 75,748 input / 11,375 output tokens.

| Ticket | Requests | Delegations | Tokens in / out | Result |
|---|---|---|---|---|
| #101 | 14 | 4 | 22,332 / 3,662 | completed, `pending_human_approval` |
| #102 | 12 | 3 | 21,243 / 2,655 | completed, `no_approval_needed` (no action proposed; see below) |
| #103 | 19 | 5 | 32,173 / 5,058 | completed, `pending_human_approval` |

**Errors:** none. There were 0 `error`, `delegation_failed`, `delegation_blocked`, or `delegation_reused` entries, and no exceptions on stderr.

**Delegation paths taken by gpt-6-luna:**
- #101: Boss → Inventory, Accounting, Customer Service; Customer Service → Inventory
- #102: Boss → Facilities, Accounting; Facilities → Accounting
- #103: Boss → Customer Service, Accounting, Inventory; Customer Service → Accounting, Inventory

**Verification after the run:**
- **Tool results match the DB:** all 39 recorded MCP results (39 `tool_call`/`tool_result` pairs, all made by agents; the guardrails made no MCP calls because no outflow had an amount) were replayed read-only against `campus_customs_new.db`, with 0 mismatches.
- **Databases unchanged:** both SHA-256s are still `23686a90…f360a`; `payments` still has 0 rows.
- **Nothing executed:**
  - Every action is `proposed` or `blocked_by_guardrail`, and every consequential action has `requires_human_approval: true`.
  - Both customer replies are drafts (`sent: false`).
  - No payment, order, or message was made, because no code path can make one.
- **Cash:**
  - No payment with an amount was proposed, so the guardrail projection had nothing to block.
  - Accounting's own projection for #102 (rent $2,400 + invoice 501 $840) ends at $160.00, never negative.
- **Guardrail activity:** two `restock_order` proposals without a cost (#101 size S reprint, #103 12× size M) were `blocked_by_guardrail` ("Cash outflows have a verifiable amount"). They appear as the 2 failed rule checks. This is the cash rule working as designed: an unpriced purchase can't be checked against cash.

**Proposals (summary):**
- **#101:**
  - Size S is out of stock; M/L/XL are available.
  - A size S reprint from Bulldog Print Co has a 5-day lead time, unconfirmed.
  - Invoice 501 is open and overdue, but not proposed for payment.
  - Proposed actions: customer reply draft and substitute-size offer (both pending approval), plus the reprint (blocked: no cost).
- **#102:**
  - Rent matches lease 1 ($2,400.00 due 2026-09-02, 2 days out), and no rent payment is on record.
  - The Boss proposed **no payment** and asks a human to confirm the combined cash projection and approve rent by 2026-09-02.
- **#103:**
  - 8 of 20 size M are in stock (12 short); other sizes S 4 / L 14 / XL 6. List price $58 ($1,160 for 20).
  - Proposed actions: a reply draft asking about size mix, partial order, and budget, plus optional 5% ($1,102) and 10% ($1,044) discount offers. All are pending human approval.
  - The restock was blocked (no cost).

**Main quality gaps (not fixed: fixing them would need another paid run):**

1. **Ticket #102 did not produce a rent payment proposal.**
   - **Expected:** a `payment` action for $2,400.00 to Elm City Properties (lease 1), pending human approval.
   - **Actual:** no proposed actions, so `approval_status` is `no_approval_needed`. The Boss's `open_questions` ask a human to confirm the combined cash projection and approve rent by 2026-09-02.
   - **Cause (from the audit trail):** Accounting ran two cash projections.
     - Via Facilities (`boss → facilities → accounting`), the task included the lease amount, and the projection of rent $2,400 + invoice 501 $840 ended at **$160.00, never negative**.
     - In the Boss's direct request (`boss → accounting`), the task did not mention the $2,400 rent. Accounting has no lease tool, so it projected only the $840 invoice (ending at $2,560.00).
     - The Boss then treated the combined figure as unverified ("Accounting could not independently verify the rent amount"), which understates what the Facilities → Accounting check showed.
   - **Safety impact:** none. No money moved, and a human still decides.
   - **Possible fix:** give Accounting read access to `get_rent_due`, or have the Boss pass one specialist's facts to the next.
2. **Ticket #103 missed the vendor lead-time information.**
   - **Expected:** Bulldog Print Co (`apparel reprint`, 5 lead days) as the restock option for the 12-hoodie shortfall.
   - **Actual:** Inventory called `list_vendors(specialty="hoodies")` twice (via Boss and via Customer Service). Both returned 0 vendors, because the specialty text is "apparel reprint". Inventory honestly reported that no vendor or lead time was available, and the proposal and customer draft say no restock estimate exists.
   - **No fabrication:** the agent reported exactly what the tool returned. In #101 the same agent searched "apparel" and found Bulldog Print Co.
   - **Possible fix:** match vendors by product category (hoodie/tee → apparel), or tell the Inventory prompt to search "apparel" for clothing.

**Other limitations:**

3. **Duplicate work.** In #101 and #103 both the Boss and Customer Service consulted Inventory with differently worded tasks, so the reuse cache (exact task text) didn't catch the repeat. Accounting also priced discounts on a single tee in #101, which the ticket didn't need.
4. **Discount `amount` meaning.** For #103 the model put the discount value in `amount` ($58.00 for 5%, $116.00 for 10%), not the order total. The descriptions and options carry the totals ($1,102.00 and $1,044.00).
5. **Unpriced restocks blocked.** The two `restock_order` proposals (#101 size S reprint, #103 size M) had no cost, so the guardrail blocked them. That is the cash rule working, but a human sees "blocked" rather than a priced option.
6. **Ticket status not updated.** Status is never written back, by design; all three tickets remain `open` in the DB.

**Files from this run** (not edited afterwards):
- `output/proposed_resolutions.json`: the three proposals.
- `output/audit_trail.json`: 200 entries, hash chain verified intact.

## Ticket plans (Problem 6)

**Deliverable:** `output/desk_tickets.html`, a self-contained page with no external resources and accessible tabs (click, arrow keys, or `#101`/`#102`/`#103`/`#cash`/`#reflection` links). Printing shows every tab.

| Tab | Contents |
|---|---|
| #101, #102, #103 | Ticket record and linked facts (each with its MCP tool) · **Expected** section (blue): first agent and why, delegation sequence, who is *not* called, MCP tools per agent with expected results, expected resolution · **Actual** section (yellow, dashed): blank headings to fill in after the agents run |
| Cash, Reflection | "Coming later" placeholders for later problems |

**How the plans were checked:**
- **Facts:** every fact on the page was re-read through the MCP server locally (read-only, no Portkey) on 2026-10-11.
- **Boundaries:** every planned delegation and tool call was checked against `DELEGATES` and `AGENT_MCP_TOOLS` in `backend/agents.py`. All are allowed, and none of the plans uses every specialist.

**Planned routing**

| Ticket | First call (why) | Delegation sequence | Not called | Key expected proposal |
|---|---|---|---|---|
| #101 | Customer Service: a customer order whose output is a reply to Tauhid | Boss → Customer Service → Inventory; Boss → Accounting (invoice 501) | Facilities; no direct Boss → Inventory | Draft reply + substitute M/L/XL; invoice 501 $840 payment proposal (overdue); no duplicate reprint order |
| #102 | Facilities: rent belongs to the lease owner | Boss → Facilities → Accounting (with the $2,400 amount) | Customer Service, Inventory; no separate Boss → Accounting | Rent **payment proposal** $2,400 to Elm City Properties by 2026-09-02; rent + invoice 501 leaves $160 |
| #103 | Customer Service: a customer request needing honest options and a reply | Boss → Customer Service → Inventory and → Accounting | Facilities; no direct Boss → Inventory/Accounting | Options: 8 M now, mix with 12 L, wait for a 12-unit restock (~5 lead days), discounts 5–15% (all above cost, human decides); draft reply |

**Lessons from the Problem 5 live run built into the plans:**
- **#102:** the Boss should not send its own Accounting request without the rent amount. That is what led to no rent payment proposal.
- **#103:** Inventory should search vendors for `"apparel"`, not `"hoodies"`.
- **Pricing restocks:** a restock needs a cost estimate (12 × $22.00 unit cost = $264.00, labelled an estimate) so the cash guardrail can check it instead of blocking it.
- **No duplicate routing:** the Boss shouldn't call Inventory or Accounting directly when Customer Service already consults them.

**What this problem changed:** the plans are documentation only. No code changed, no agents ran, and no Portkey calls were made. `proposed_resolutions.json`, `audit_trail.json` (200 entries), and both databases are untouched.

## Backend routes (Problem 7)

**Run** (from `Homework-5/backend`, with the HW5 venv): `uvicorn main:app --reload --port 8000` → `http://localhost:8000` (interactive docs at `/docs`). CORS allows the Vite dev server (`http://localhost:5173`).

### Routes (one per line)

- `GET  http://localhost:8000/api/health`: service status (model `gpt-6-luna`, whether a Portkey key is configured: true/false only, database file name).
- `GET  http://localhost:8000/api/tickets`: all tickets with `open`/`resolved` status, each one's latest agent run, and a proposal summary (approval status, number of approvable actions).
- `GET  http://localhost:8000/api/tickets/{ticket_id}`: one ticket, its run status, and its full latest proposal; each action has an `action_id` (`<run_id>:<index>`), approval state, and an `approvable` flag.
- `POST http://localhost:8000/api/tickets/{ticket_id}/run`: runs the existing agent team on an open ticket (body `{"wait": false}` → 202 then poll; `{"wait": true}` → 200 with the proposal). Only proposes; executes nothing.
- `GET  http://localhost:8000/api/events?ticket_id=&after_seq=&limit=`: recent agent events from the audit trail (what each agent said, delegations, tool calls with args and results, guardrail checks, approvals), with `last_seq` for polling.
- `POST http://localhost:8000/api/approvals`: a human approves one proposed payment or purchase (`ticket_id`, `action_id`, exact `amount`, `approved_by`, `confirm: true`, optional `resolve_ticket`). It records the payment, deducts checking, and can mark the ticket resolved.
- `GET  http://localhost:8000/api/cash`: current checking balance from `cash_accounts` (via MCP).
- `POST http://localhost:8000/api/reset`: body `{"confirm": true}`; restores the working DB from the original values (the original is only read).

### How it builds on Problems 3–6

- **Reads go through MCP:** the API calls the `campus-customs` MCP server in-process (`fastmcp.Client(server.mcp)`), the same server and tools the agents use. One read-only tool was added, `list_tickets(status)`, so the dashboard can list resolved tickets too. No agent's allowlist includes it.
- **Runs use the existing `Team`:** each run uses `backend/agents.py` (stdio MCP, delegation limits, guardrails, audit trail) unchanged, and saves the proposal through `backend/proposals.py` (shared with the CLI). Before a run, unapproved payments proposed for *other* tickets are passed to the cash guardrail, because a human could still approve all of them.
- **Writes are confined to `backend/ledger.py`,** which is called only by `POST /api/approvals` and `POST /api/reset`. No agent tool reaches it, and the MCP server stays read-only.
- **Database path:** the working DB is `data/campus_customs_new.db`. `CAMPUS_CUSTOMS_DB` can point the server, ledger, and agents at a test copy, but both the MCP server and the ledger raise if it names the original.

### Approval safeguards (`POST /api/approvals`)

1. **Explicit human action:** `confirm` must be the literal `true`. `approved_by` is required (2–80 characters) and may not be an agent or system name (`boss`, `inventory`, …, `agent`, `system`, `bot`). Unknown fields are rejected.
2. **Proposal check:** the action must be in the ticket's **latest** proposal; an action id from an older run returns 409.
   - It must be a `payment` or `restock_order`, with status `proposed` (not `blocked_by_guardrail`).
   - It must not already have been approved since the last reset.
   - `amount` must equal the proposed amount.
3. **Database check (via MCP):** the payment must match a record linked to the ticket.
   - An invoice must be the ticket's invoice, still `open`, with the same amount.
   - Rent must be the ticket's lease, the same amount as `monthly_rent`, and not already paid.
   - A purchase is recorded as `purchase` against the ticket.
   - An unidentifiable payment returns 422.
4. **Cash check:** MCP `project_cash_balance` must stay non-negative.
5. **Atomic write:** inside one `BEGIN IMMEDIATE` transaction, the ledger re-checks balance, invoice, and rent, inserts the `payments` row (with `approved_by`), sets the invoice `paid` if relevant, and deducts checking. The `UPDATE ... WHERE balance - amount >= 0` makes going negative impossible even under a race. It optionally marks the ticket `resolved`, then commits. Any failure rolls back with no change.
6. **Audit:** success is logged as `human_approval` (with balance before and after). Every refusal after body validation is logged as `human_approval_rejected` with the reason. Approval state is derived from the audit trail since the last `database_reset`.

Other guards:
- One agent run at a time (409 if busy).
- Only `open` tickets can be run (409 for resolved).
- No reset during a run.
- Approvals and resets are serialized.
- 503 with a clear message if `PORTKEY_API_KEY` is missing.
- Agent failures return 502 and are recorded on the run and in the audit trail.

### Tests (offline, no Portkey): `python -m pytest -q` → **64 passed**

- **New `tests/test_api.py` (24 tests).** Each test uses a temp DB copy, temp audit trail, and temp proposal store, with scripted models over real MCP stdio. Covered:
  - health shows no key
  - ticket list and DB match
  - ticket-id validation (404/422)
  - cash matches the DB
  - synchronous run → proposal and events, including `after_seq` and `limit` validation
  - background run plus polling
  - second run while busy → 409, and reset while busy → 409
  - missing key → 503
  - approving a rent proposal from a real run → payment row, cash $3,400 → $1,000, ticket resolved; a repeat → 409; resolved ticket can't be rerun
  - invoice approval (invoice → `paid`, $2,560) and a purchase that would overdraw → 409 with nothing changed
  - 10 body-validation cases
  - non-payable, blocked, overstated, unidentifiable, and unlinked proposals all refused
  - no proposal → 404
  - reset → bytes identical to the original, payments cleared, invoice reopened, tickets open, earlier approvals no longer apply
  - audit chain intact after runs, approvals, refusals, and reset
- **`tests/test_mcp_tools.py`** gained 3 tests: `list_tickets` matches the DB, no agent has it, and the DB override can't point at the original.
- **Real DBs unchanged:** the autouse fixture asserts both real DB files are byte-for-byte unchanged after every test.

### Manual check (2026-10-11)

`uvicorn main:app --reload --port 8010` was started from `backend/`. Port 8000 was occupied by the still-running Homework 4 backend, so a spare port was used. Read-only requests against the real working DB returned:
- health 200
- cash $3,400.00
- tickets #101–#103 `open`
- events from the 200-entry audit trail
- 404/422 on bad input
- `/docs` 200

No run, approval, or reset was sent, and the server was stopped afterwards.

The Problem 5 live-run proposals have **no approvable action**: no payment carried an amount, as noted in that section. A fresh run is needed before the dashboard can show an approval.

### Problem 7 review (2026-10-11)

**Route check:** the 8 routes listed above were compared programmatically with the routes FastAPI actually registers. They match exactly, one line each.

**Write boundaries, verified in code and tests:**
- **One writable connection:** the app opens exactly one writable SQLite connection, in `backend/ledger.py`.
- **MCP server is read-only:** its only connection uses `mode=ro`.
- **SQL writes:** `INSERT`/`UPDATE` exist only in `ledger.py`.
- **Two callers:** `ledger.execute_approved_payment` is called only by `POST /api/approvals`, and `ledger.reset_working_db` only by `POST /api/reset`.
- **Agents can't reach it:** `agents.py`, `guardrails.py`, and `models.py` never reference the ledger.
- **Original refused:** both the ledger and the MCP server refuse a path that resolves to `data/campus_customs.db`.

**Fix made in the review:**
- Before: an oversized `ticket_id` in the approval body (e.g. 10^20) got as far as SQLite. It still returned 422, but via an `OverflowError` traceback in the server log.
- After: `ApprovalRequest.ticket_id` and the `/api/events` `ticket_id` filter are bounded (≤ 1,000,000) like the path parameter, so bad ids are rejected during request validation.

**Tests:** `python -m pytest -q` → **68 passed** (64 + 4 new review tests). No Portkey calls; agent runs use scripted models over real MCP stdio, on temp DB copies.

| Requirement | Covered by |
|---|---|
| Ticket list with open/resolved status | `test_list_tickets`, `test_approve_rent_from_a_real_run` (shows `resolved`) |
| Run the agent team on a ticket | `test_run_agents_and_events` (wait), `test_background_run_then_poll` (202 + poll), `test_second_run_while_one_is_running_is_refused`, `test_missing_portkey_key_gives_503` |
| Recent agent events | `test_run_agents_and_events` (agents, tools, messages, `after_seq`, `limit`) |
| Unapproved actions refused | `confirm` false/missing → 422, agent/system names as `approved_by` → 422, no proposal → 404 (`test_approval_validation`, `test_no_proposal_means_nothing_to_approve`); agents have no write path (`test_only_the_ledger_writes_to_a_database`) |
| Duplicate approvals refused | `test_approve_rent_from_a_real_run` (second approval → 409, cash unchanged) |
| Invalid proposals refused | non-payable kind, `blocked_by_guardrail`, overstated invoice, unidentifiable payment, lease not linked to the ticket, wrong amount, unknown or stale action id (`test_only_valid_payable_proposals_can_be_approved`, `test_approval_validation`) |
| Cash never negative | API: purchase of $2,600 against $2,560 → 409, nothing recorded (`test_approve_invoice_and_purchase_and_cash_floor`). Ledger alone with API checks bypassed: $3,400.01 against $3,400 → 409 and rolled back (`test_ledger_itself_refuses_an_overdraw`) |
| Checking balance | `test_cash_matches_db`, balances after each approval |
| Reset | `test_reset_restores_original_values` (bytes identical to the original, payments cleared, invoice reopened, tickets open, earlier approvals no longer count), no reset during a run |
| Original DB never written | `test_ledger_refuses_the_original_database`, `test_db_override_can_never_point_at_the_original`, and the autouse fixture asserting both real DB files are byte-identical after every test |

### Known limitations (Problem 7)

1. **Approvers are not authenticated.** "Explicit human action" is enforced by the request shape only:
   - `confirm` must be the literal `true`;
   - `approved_by` is a required name and can't be an agent or system name.

   There is no login, session, or password, so anyone who can reach the API can submit an approval under any name. The safeguards limit *what* can be approved (an existing, valid, unapproved proposal with the exact amount, and enough cash), not *who* approves. The name is recorded in `payments.approved_by` and the audit trail, but it isn't verified. This is acceptable for a local single-user dashboard bound to `localhost`, but not for a shared deployment, which would need real authentication and roles.
2. **Approving while a run is in progress isn't blocked.** A human can approve an action from the current proposal while a new run for the same ticket is working. The approval is still validated against the database, and paid invoices or rent can't be paid again, but a new run could propose another purchase that a human could also approve.
3. **Run status is held in memory.** It is lost on a server restart (including `--reload` after a backend file change). Proposals and events persist on disk.
4. **Only tickets with a payment or purchase can be resolved.** Approving one marks the ticket resolved; there's no route to resolve a ticket that has none.
5. **No approvable proposal exists yet.** The stored Problem 5 live-run proposals have no payment with an amount, so a fresh agent run (Portkey calls) is needed before an approval can be shown on real data.

### Port 8000 status (checked 2026-10-11, not changed)

Port 8000 is held by the **Homework 4** backend:
- `uvicorn main:app` from `Homework-4/backend`, pid 19268 (+ reload worker 19278), started 2026-10-07.
- It was launched from a terminal of an earlier Claude session; it isn't in this session's terminal tabs.
- It still answers as "Campus Customs API" (HW4 routes).

It was left running. To start Homework 5 on the required port:
1. Stop HW4 with Ctrl+C in its terminal, or `kill 19268`.
2. From `Homework-5/backend` with the HW5 venv active, run `uvicorn main:app --reload --port 8000`.

The HW5 server was verified earlier with the same command on spare port 8010.

### Problem 7 final check (2026-10-11)

- **Port 8000 is now free.** The Homework 4 server noted above is no longer listening. Nothing was stopped by this check.
- **Startup verified with the exact assignment command:** `uvicorn main:app --reload --port 8000`, run from `Homework-5/backend` with the HW5 venv, started cleanly ("Application startup complete") at `http://localhost:8000`.
- **Read-only requests against the real working DB:**
  - `GET /api/health` and `GET /api/cash` returned 200 (checking $3,400.00).
  - `GET /api/tickets` returned #101–#103, all `open`.
  - `GET /api/tickets/102` returned 200, `GET /api/events` returned 200 (last seq 199), and `/docs` returned 200.
  - Unknown ticket → 404; invalid ids → 422.
  - Request bodies that fail validation (`confirm: false` on approvals, reset without confirm, a run with an extra field) → 422 before anything ran.

  No run, approval, or reset was performed, and the server was stopped afterwards.
- **Tests:** 68 passed. Both DB files still hash `23686a90…f360a`; the audit trail (200 entries) and proposals were unchanged.

## Agent dashboard (Problem 8)

**Frontend:** `frontend/`, React 19 + Vite 8 + TypeScript 6 (same toolchain as Homework 4), no UI library, no runtime downloads (system fonts, inline SVG icons). The design rationale is in `output/design.md`.

### Run it

1. **Backend**, from `Homework-5/backend` with the HW5 venv: `uvicorn main:app --reload --port 8000`.
2. **Frontend**, from `Homework-5/frontend`: `npm install` (first time), then `npm run dev`.
3. Open the URL Vite prints, normally `http://localhost:5173`.

API base: `src/api.ts` uses `VITE_API_BASE` or defaults to `http://localhost:8000`.

**CORS change (`backend/main.py`):**
- The fixed origin list was replaced by `allow_origin_regex = ^http://(localhost|127\.0\.0\.1):517[3-9]$`, allowing the Vite dev origin and the next ports Vite falls back to when 5173 is busy.
- Methods are GET/POST; headers are `Content-Type`/`Accept`.
- New test `test_cors_allows_the_vite_dev_origin_only`: 5173/5174 are allowed; other hosts, ports, https, and `:51730` are refused.
- CORS is not authentication, and no approval safeguard changed.

### Important components

| File | Role |
|---|---|
| `src/api.ts` | Typed client for the Problem 7 routes only. Errors become `ApiError` (status 0 = backend unreachable) with the backend's message. |
| `src/useDesk.ts` | All state and polling. ~1.2 s while any run is `running`, otherwise 6 s. Events are fetched incrementally with `after_seq`. Exposes `startRun`, `approve`, `reset`. |
| `src/lib/activity.ts` | Pure functions: `groupRuns` (audit events → runs), `buildFeed` (pairs tool calls with results; handoffs, reports, checks, markers), `crewState` (who worked, who is working, tools, summaries, who called whom), `resultHighlights` (key fields per MCP tool). |
| `src/components/TopBar.tsx` | Masthead and **cash ledger**: checking balance, total awaiting approval, balance if all approved; flashes when the balance changes. Desk tools menu with reset. |
| `src/components/TicketQueue.tsx` | Three ticket cards with Open/Resolved pill and run/proposal badge. |
| `src/components/CaseFile.tsx` | Ticket header, confirmed **Run the agent team**, run history tabs, crew strip, live activity timeline, crew report. |
| `src/components/DecisionPanel.tsx` | Proposal summary and recommendation; **payment slips** with the approve dialog (name + explicit checkbox + cash preview); other actions with reasons; draft reply; rule checks; key facts; open questions; empty states. |
| `src/components/Dialog.tsx`, `Notices.tsx` | Accessible modal; toasts; offline banner. |

### API routes used (all from Problem 7; nothing else is called)

| Route | Used for |
|---|---|
| `GET /api/health` | backend status and model in the masthead |
| `GET /api/tickets` | ticket queue, open/resolved status, run and proposal badges |
| `GET /api/tickets/{id}` | case file and decision panel (proposal, action ids, approvable flags, approvals) |
| `POST /api/tickets/{id}/run` | `{"wait": false}`, only after the confirmation dialog |
| `GET /api/events?ticket_id=&after_seq=&limit=` | live activity feed, crew strip, crew report |
| `POST /api/approvals` | `{ticket_id, action_id, amount, approved_by, confirm: true, resolve_ticket}`, only from the approve dialog |
| `GET /api/cash` | checking balance |
| `POST /api/reset` | `{"confirm": true}`, only after typing RESET |

### Checks (no Portkey calls)

- **`npm run typecheck`** (tsc -b): pass.
- **`npm run lint`** (oxlint): 0 warnings.
- **`npm run build`**: pass (≈265 kB JS / 82 kB gzip).
- **`npm test`** (Vitest + Testing Library + jsdom): **21 passed**.
  - Activity logic, against real snapshotted events: runs and stats, tool and result pairing, handoffs and reports, pending calls, crew state for #102 (Facilities and Accounting worked; Customer Service and Inventory not needed), result highlights.
  - Dashboard with a mocked backend built from real API snapshots (`src/test/fixtures.json`):
    - three tickets, Open status, desk date, and $3,400.00;
    - case file with real activity, and no POST requests while selecting tickets;
    - empty state when nothing is approvable;
    - a run starts only after confirmation;
    - approval needs a name and the checkbox, sends the exact body, then shows $1,000.00, "Approved by", and Resolved, with the run button disabled;
    - a backend refusal (409) is shown in the dialog;
    - an overdraw is blocked in the UI;
    - the offline banner appears;
    - an error toast appears;
    - reset requires typing RESET.
  - Test-only approvable payments are added inside the tests; the real proposals have none.
- **Backend `python -m pytest -q`:** **69 passed** (68 + the CORS test).

### Verified against the real backend (2026-10-11)

- **Setup:** `uvicorn main:app --reload --port 8000` and `npm run dev` were run against the real working DB and audit trail. The page was viewed in the Claude app's Browser pane through a small local proxy on port 5175, because its sandbox can't read the Desktop folder.
- **What it showed:**
  - $3,400.00, desk day Mon, Aug 31, 2026, and #101–#103 Open;
  - the real Problem 5 runs, e.g. #101: 14 model calls, 4 handoffs, 30 feed rows, crew report for Boss / Customer Service / Inventory / Accounting; #102: only Boss, Facilities, Accounting;
  - the "Nothing to approve" empty state.
- **Clean run:** no console warnings or errors; no horizontal overflow at 375 px.
- **Read-only:** the backend log shows **140 GET and 0 POST** requests during the session, so nothing was run, approved, or reset. Both DBs, the audit trail (200 entries), and the proposals were byte-identical afterwards.
- **Shutdown:** the servers were stopped afterwards. The cleanup command used a broad `pkill -f vite` pattern, which also stopped the Lecture 10 Vite dev server that had been running on `127.0.0.1:5173`; that was not intended.

### Limitations

1. **No approvable payment in the current data.** The saved proposals (Problem 5 live run) have no payment or purchase with an amount, so the dashboard shows the empty state. Seeing a real approval needs a new agent run (Portkey), which only happens when the Run button is pressed and confirmed. The approval UI is covered by tests with test-only proposals.
2. **A live run hasn't been watched in the browser.** Live streaming is covered by tests (pending tool calls, the working crew state, the `after_seq` polling path) and by the real recorded runs, but an actual gpt-6-luna run was not started.
3. **Polling, not push.** About 1.2 s latency during runs; there's no websocket or SSE endpoint in the backend.
4. **Port 5173 sharing.** If another dev server holds `127.0.0.1:5173` (as Lecture 10 did), Vite may bind `localhost`/`::1:5173` alongside it. Then `http://localhost:5173` reaches this dashboard but `http://127.0.0.1:5173` reaches the other app. Stopping the other server avoids the confusion.
5. **Inherited from Problem 7:** approvers aren't authenticated (the typed name is recorded, not verified), and run status is lost if the backend restarts.

### Troubleshooting notes (Problem 8)

**Accidental stop of the Lecture 10 Vite dev server (2026-10-11).**

- **What was running:** the user's Lecture 10 frontend dev server.
  - pid 17517, started 2026-09-30.
  - Working directory: `../../Lectures/Lecture-10/mult_agent_hp/frontend` (relative to `Homework-5/`).
  - Command: `node .../node_modules/.bin/vite --host 127.0.0.1 --port 5173`, listening on `127.0.0.1:5173`.
  - It was unrelated to Homework 5, and the user had not authorized stopping it.
- **What happened:** after the Problem 8 browser check, the HW5 servers I had started were stopped with pattern-matching commands, including `pkill -f "vite" -P <pid>`. On macOS, `pkill` stops reading options at the first non-option argument, so `-P <pid>` was treated as extra *patterns* instead of a parent-process filter. The command therefore stopped **every** process whose command line contained "vite", including the Lecture 10 server.
- **How it was found:** a follow-up port check showed nothing listening on 5173, and pid 17517 no longer existed.
- **Impact:**
  - The Lecture 10 dev server is down until it is restarted.
  - No files were changed. Its project and node_modules are untouched, and no Homework 5 data, audit trail, or proposals were affected.
  - The HW4 backend had already been stopped by the user before this, so it wasn't involved.
- **Not restarted.** The user will decide when. To restart it exactly as it was:

  ```bash
  cd ../../Lectures/Lecture-10/mult_agent_hp/frontend && npx vite --host 127.0.0.1 --port 5173  # run from Homework-5/
  ```

  `npx vite` runs that project's own `node_modules/.bin/vite`, the same binary as before. Note that with Lecture 10 back on `127.0.0.1:5173`, HW5's `npm run dev` will share 5173 on `localhost`/`::1` (see limitation 4 above). Start HW5 first, or stop Lecture 10 while using the dashboard, to avoid confusion.
- **Prevention, applied from now on:**
  - Record the PID of anything started (`$!` or `lsof -t -iTCP:<port>`) and stop only that exact PID.
  - Check the target's command and working directory before stopping it.
  - Never use `pkill -f` or other broad process matching.
  - Ask before stopping anything not started in this session.

### Problem 8 final review (2026-10-11)

I don't have the assignment page itself, so this review checks the requirements in the Problem 8 prompt. No servers were started, nothing was stopped, and no Portkey calls were made.

| Requirement | Evidence |
|---|---|
| React + Vite + TypeScript in `frontend/`, runs with `npm run dev` | Vite 8 / React 19 / TS 6. `npm run dev` served the dashboard during the earlier browser check. |
| Lists all three tickets with open/resolved status | Test: "shows the three tickets, their status, the desk date and the checking balance". Browser check: #101–#103 Open. |
| Select a ticket and run the team via Problem 7 | Tests: selecting sends **no POST**; a run starts only after confirmation, as `POST /api/tickets/{id}/run {"wait": false}`. |
| Agent activity (what agents say and do, tool calls, results), auto-refresh | `buildFeed`/`crewState` tests on real events; polling every ~1.2 s while running (`after_seq`), 6 s otherwise; browser check showed the real #101 feed (30 rows). |
| Summary of each agent after a run | Crew report test; browser check showed 4 agent cards for #101. |
| Checking balance shown prominently and updated after approval | Test: $3,400.00 → $1,000.00 after approval; the ledger flashes on change. |
| Human approval through the existing route, with amount, purpose, details, status | Test: the approve button stays disabled until a name and the checkbox are given; exact body to `POST /api/approvals` with `confirm: true`; "Approved by …" stamp; refusal shown; overdraw blocked in the UI. |
| Resolved status shown when the backend reports it | Test: after approval the backend reports `resolved`, so the card shows Resolved and Run is disabled. |
| Loading, empty, error, failed-request states | Tests: offline banner, error toast, nothing-to-approve empty state. Loading skeletons were seen in the browser; no automated test covers them. |
| Uses the Problem 7 API only, no database access | `src/api.ts` holds the app's only `fetch`, to `VITE_API_BASE` (default `http://localhost:8000`) + `/api/...` (8 routes). There is no other network or file access in `src/`. |
| No invented proposal or automatic paid run | Empty-state test. Runs need an explicit button and confirmation. |

**Results:** frontend typecheck pass, lint 0 warnings, build pass, **21/21** tests; backend **69/69**. Both DBs, the audit trail (200 entries), proposals, smoke tests, and ticket plans were byte-identical before and after.

## Resolving the tickets (Problem 9) and final summary

### Preparation (before any paid call)

1. **Reset.** `data/campus_customs_new.db` was reset from the dashboard's *Reset working database* control (`POST /api/reset`, audit seq 200).
   - The working DB hash equals the original (`23686a90…f360a`); the original was only read.
   - **Starting checking balance: $3,400.00** (`cash_accounts`, as of 2026-08-31). 0 payments, tickets 101–103 open, invoice 501 open ($840).
2. **Review of guardrails and the approval flow.** It found two blockers. The user chose all three recommended options in chat.
   - **Agent changes made for the known gaps (read-only).** These were *attempted* fixes; whether each worked is from the live runs below.
     - Accounting may read `get_rent_due`, so it verifies rent itself. **Worked:** #102 produced a priced $2,400.00 rent payment.
     - The Accounting prompt says to price restocks as qty × `unit_cost`, labelled an estimate. **Did not work:** #103's restock was still proposed without a cost and blocked. The same prompt also says to give each payment `amount`, `payee`, and `ref` = `invoice <id>`/`lease <id>`, which the #102 payment followed.
     - The Inventory prompt says to search vendor specialties by category (`"apparel"`), falling back to an unfiltered `list_vendors()`. **Worked:** #101 and #103 both found Bulldog Print Co (5 days).
     - The Facilities prompt says to use the lease amount, the landlord as payee, and `ref` = `lease <id>`. **Worked** (#102: `ref` `lease 1`).
     - The Boss prompt says not to send Accounting a separate money question when a specialist already consults it with full facts, and that every payment or restock must carry a verified amount. **Did not work:** Boss still sent parallel duplicate requests on all three tickets, and #103's restock had no amount.
     - **Not addressed:** #101's overdue invoice 501. No change targeted it, and it was not proposed for payment.
   - **Human-approved resolution added:** `POST /api/tickets/{id}/resolve` + `ledger.resolve_ticket` + a dashboard dialog.
     - It requires `confirm: true`, a human `approved_by` (agent and system names rejected), and the **latest** `run_id` (409 otherwise).
     - The ticket must be open and no run may be in progress for it.
     - Pending approvable payments must be explicitly acknowledged as left unpaid.
     - It is recorded as `human_resolution` (refusals as `human_resolution_rejected`).
     - It changes only `tickets.status`, **never cash, payments, or invoices**.
   - **Approver:** the user approved each payment and each resolution individually in chat before it was entered in the dashboard. Nothing was approved on the user's behalf.
3. **Offline checks.** Backend `pytest` → **78 passed** (69 + 9 resolve tests); frontend typecheck, lint (0 warnings), build, and `vitest` → **23 passed** (21 + 2 resolve-dialog tests).

### The runs (gpt-6-luna via Portkey, from the dashboard)

Each ticket was run **once**; no ticket was rerun.

| Ticket | Run | Model requests | Tokens in / out | Delegations | Not called | Errors |
|---|---|---|---|---|---|---|
| #101 | `b0286d37ec2e` (seq 201–257) | 14 | 22,911 / 3,366 | Boss→Inventory, Boss→Customer Service, Customer Service→Inventory, Customer Service→Accounting | Facilities | none |
| #102 | `5c66edf270c9` (seq 258–318) | 12 | 23,235 / 2,370 | Boss→Facilities, Boss→Accounting, Facilities→Accounting | Customer Service, Inventory | none |
| #103 | `5a2a491de789` (seq 321–391) | 15 | 29,202 / 4,379 | Boss→Customer Service, Boss→Accounting, Boss→Inventory, Customer Service→Accounting | Facilities | none |
| **Total** | | **41** | **75,348 / 10,115** | 11 | | **0** |

The MCP calls, agent reports, and plan-vs-actual comparison for each ticket are in the **Actual** tabs of `output/desk_tickets.html` and in `output/resolved_tickets.json`.

### Outcomes

| Ticket | Proposal | Human decision | Final status | Cash |
|---|---|---|---|---|
| #101 | Draft reply (not sent): size S out of stock, offer M 5 / L 3 / XL 2 or a size S reprint (Bulldog Print Co, 5 days). No payment proposed; invoice 501 reviewed but not proposed. | Resolution approved by Navya Sharma (seq 320) | **resolved** | $0.00 |
| #102 | $2,400.00 rent payment to Elm City Properties, `lease 1`, verified by Facilities and Accounting; projection $3,400 → $1,000 ($160 with invoice 501). | Payment approved by Navya Sharma, payment #1, ticket resolved (seq 319) | **resolved** | −$2,400.00 |
| #103 | Draft list-price quote ($58, $1,160 for 20), 12 size M short (~5 days, earliest 2026-09-05); 5% discount ($1,102) as a human decision only; 12-unit restock **blocked** (no verified cost). | Resolution approved by Navya Sharma (seq 392); discount not granted, nothing ordered | **resolved** | $0.00 |

**Cash reconciliation:**
- $3,400.00 − $2,400.00 (#102 rent, payment #1) − $0 (#101) − $0 (#103) = **$1,000.00**, equal to `cash_accounts.balance` in `data/campus_customs_new.db`.
- `payments` holds exactly one row (rent, lease 1, $2,400.00, approved_by Navya Sharma). The lowest balance reached was $1,000.00.
- Invoice 501 ($840, overdue) is still open and unpaid.

**Integrity:**
- The audit trail grew from 200 to **393** entries, append-only; the first 200 are byte-identical and `AuditTrail.verify()` → intact.
- The original `data/campus_customs.db` is unchanged.
- The backend received exactly these writes: 1 reset, 3 runs, 1 payment approval, 2 resolutions. A further `POST …/resolve` with an empty body was a pre-run probe, rejected with 422 at validation.
- Processes were started and stopped by exact PID (backend 51335, npm 51336, Vite 51357, plus the Browser-pane proxy). No other process was touched.

**Deliverables:**
- `output/resolved_tickets.json`;
- `output/resolved_board.html` with 14 real dashboard screenshots in `output/screenshots/`;
- the Actual and Cash tabs in `output/desk_tickets.html` (Expected sections byte-identical to Problem 6).

### Problem 9 limitations and observations

1. **#101 resolved without paying invoice 501.** The team reviewed the overdue $840 invoice for the size S reprint but didn't propose paying it. Closing #101 leaves that payable open.
2. **#103's restock had no cost, and the Problem 9 pricing change did not fix it.** Inventory proposed sourcing 12 hoodies without an amount, and Accounting wasn't asked to price it, so the cash guardrail blocked it (correctly). The restock-pricing guidance added to the Accounting prompt never took effect, so this gap is **still open**. The team also didn't offer the "8 M + 12 L" mix my plan expected.
3. **Boss still double-routes.** In all three tickets it sent some specialists work in parallel that another specialist also requested (11 delegations vs 8 planned). It cost extra model calls but caused no errors.
4. **Accounting over-explored discounts** on #103 (11 tool calls, discount levels up to 62%).
5. **The remaining limitations from Problems 7–8 still apply:** approvers aren't authenticated (the typed name is recorded, not verified), run status lives in memory, and the feed polls rather than streams.

### Final summary of the system

- **Database (9 tables), `data/campus_customs_new.db`:**

  | Table | Holds |
  |---|---|
  | `desk` | "today" |
  | `inventory` | stock by sku/size |
  | `pricing` | cost and list price |
  | `vendors` | lead times |
  | `leases` | rent |
  | `cash_accounts` | checking |
  | `payments` | human-approved outflows |
  | `invoices` | vendor payables |
  | `tickets` | the work queue |

  The original `data/campus_customs.db` is only ever read (as the reset source).
- **MCP server `campus-customs` (12 read-only tools):**
  - check_stock, get_rent_due, quote_bulk_order (P3);
  - list_open_tickets, get_ticket, get_cash_position, get_invoice, list_open_invoices, list_payments, list_vendors, project_cash_balance (P5);
  - list_tickets (P7, dashboard only).

  The DB is opened `mode=ro`, and a path to the original is refused.
- **Five agents (PydanticAI, gpt-6-luna via Portkey):**

  | Agent | MCP tools | May delegate to |
  |---|---|---|
  | Boss | get_ticket, list_open_tickets | all four specialists |
  | Customer Service | get_ticket | Inventory, Accounting |
  | Inventory | check_stock, list_vendors | none |
  | Accounting | cash, invoices, payments, projection, quotes, and get_rent_due (P9) | none |
  | Facilities | get_rent_due, list_payments | Accounting |

  Code-enforced limits: no cycles, depth ≤ 3, ≤ 8 delegations per ticket, repeat requests reused, and one usage budget per ticket (40 requests / 60 tool calls).
- **API (`backend/main.py`, `uvicorn main:app --reload --port 8000`):**
  - `GET /api/health`, `GET /api/tickets`, `GET /api/tickets/{id}`, `POST /api/tickets/{id}/run`, `GET /api/events`, `GET /api/cash`;
  - `POST /api/approvals` (human payment or purchase);
  - `POST /api/tickets/{id}/resolve` (human resolution, P9);
  - `POST /api/reset`.

  Only `backend/ledger.py` writes, and only for approvals, resolutions, and resets.
- **Dashboard (`frontend/`, `npm run dev`):**
  - ticket queue, case file with live crew strip and activity feed, crew report;
  - decision panel with payment slips, approve and resolve dialogs, and the cash ledger;
  - loading, empty, offline, and error states. Design rationale in `output/design.md`.
- **Safety rules:**
  - Agents only propose. Payments and purchases need an explicit human approval (name + confirm + exact amount, validated against the linked invoice or lease and the cash balance). Resolutions need an explicit human approval of the latest run.
  - Cash can never go negative: checked by the guardrails before proposing, by MCP projection before approval, and in the ledger's transaction.
  - There are no send, email, or ordering tools, so no customer or vendor is ever contacted, and customer replies are drafts.
  - The append-only, hash-chained audit trail records every step.
- **Tests (final):** backend `python -m pytest -q` → **78 passed**; frontend `npm run typecheck` / `npm run lint` / `npm run build` → pass, `npm test` → **23 passed**.

**Test isolation fix (after the runs).**
- **Problem:** rerunning the backend suite after Problem 9 gave 39 failures. The tests had assumed `data/campus_customs_new.db` still held the original values, but it now legitimately holds the Problem 9 outcomes ($1,000.00, all resolved). One failure even showed correct behavior: with $1,000 in checking, the guardrail blocks a $2,400 rent proposal.
- **Fix:** `tests/conftest.py` now gives every test a fresh temporary copy of the **original** database through `CAMPUS_CUSTOMS_DB`, and `tests/test_api.py` copies the original rather than the working DB. No application code changed.
- **Result:** **78 passed**. The real working DB (hash `e273b319…`, the Problem 9 end state) and the original (`23686a90…`) were unchanged by the tests.

## Reflection (Problem 10)

**Status: completed (2026-10-11).** The reflection was written by Navya Sharma and saved verbatim in the **Reflection** tab of `output/desk_tickets.html`. The tab no longer says "Coming later", and the "(later)" label was removed.

- **Structure:** one card per question, headed by the question.
  1. How would I evaluate the performance of the agents on each ticket, and why?
  2. How did the actual outcome for each ticket compare with my Expected plan?
  3. What would have been simpler with one agent and tools, and why?
  4. What are three new Campus Customs problems the agent team could solve with the tools already built?
  5. What are three new Campus Customs problems the agent team could not solve with the current tools, and what additional tools and agents would be needed?

  There is no separate overall-reflection section; each closing paragraph stays under its own question.
- **Formatting only:** bullets became lists with their lead label in bold, and multi-paragraph bullets stay together. The wording is unchanged: the saved text matched the submitted reflection word for word (1,962 words, plus the title as the tab heading).
- **Unchanged:** the Expected plans (Problem 6), the Actual and Cash tabs (Problem 9), and all other sections. The HTML is still balanced and the tab script valid.
- **Not touched:** no database, payment, ticket status, proposal, audit-trail, or screenshot was changed. No Portkey calls were made.
