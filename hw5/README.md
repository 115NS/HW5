# Homework 5: Campus Customs Multi-Agent Operations Desk

A team of five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) resolves Campus Customs shop tickets.

- **Data path:** every shop fact comes through a read-only **MCP server** over a SQLite database.
- **Interfaces:** a **FastAPI** backend exposes the team to a **React + Vite + TypeScript** dashboard.
- **Agents only propose.** Payments, purchases, and ticket resolutions need an explicit human approval, and checking can never go negative.
- **Model:** `gpt-6-luna` through Portkey's OpenAI-compatible endpoint (`https://api.portkey.ai/v1`).

The full technical record (database, tools, agents, routes, safety rules, tests, outcomes) is in [`output/harness.md`](output/harness.md); the dashboard design is in [`output/design.md`](output/design.md).

## Project layout

```
Homework-5/
├── AI_prompts.md            prompt log (one section per problem)
├── README.md                this file
├── requirements.txt         Python dependencies
├── .env.example             environment template (placeholders only)
├── .gitignore
├── .mcp.json                Claude Code MCP config (start Claude Code in Homework-5/)
├── data/
│   ├── campus_customs.db        original database (read only; never written)
│   └── campus_customs_new.db    working copy (holds the final Problem 9 state)
├── mcp_server/              FastMCP server: 12 read-only tools (see mcp_server/README.md)
├── backend/                 agents, guardrails, audit trail, ledger, FastAPI app
│   └── prompts/             one prompt file per agent
├── frontend/                React + Vite + TypeScript dashboard (see frontend/README.md)
├── tests/                   backend tests (temp DB copies, scripted models, no Portkey)
└── output/                  deliverables: desk_tickets.html, harness.md, design.md,
                             resolved_tickets.json, resolved_board.html, screenshots/,
                             audit_trail.json, proposed_resolutions.json, mcp_smoke.json
```

## 1. Install

Tested with Python 3.14 and Node 24. From `Homework-5/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cd frontend && npm install
```

## 2. Configure environment variables

```bash
cp .env.example .env
```

- **`PORTKEY_API_KEY` (required):** edit `.env` and set it to your own Portkey key. `.env` is git-ignored; never commit it. The backend never returns or logs the key; `GET /api/health` only reports whether one is set.
- **`VITE_API_BASE` (optional):** the dashboard calls `http://localhost:8000` by default. To change it, copy `frontend/.env.example` to `frontend/.env.local`.
- **`CAMPUS_CUSTOMS_DB` (optional, tests only):** an absolute path to another working copy. The tests set this to a temporary copy of the original database.

## 3. Start the MCP server (optional)

You don't need to start it by hand. The agents start `mcp_server/server.py` themselves over stdio for every run, and the backend calls it in-process for reads. To run it on its own:

```bash
python mcp_server/server.py
```

That runs it over stdio. Add `--http` to serve it at `http://127.0.0.1:8002/mcp` instead:

```bash
python mcp_server/server.py --http
```

For Claude Code, `.mcp.json` registers it as `campus-customs`. Start Claude Code **in `Homework-5/`** and approve the server.

## 4. Start the FastAPI backend

From `Homework-5/backend/`, with the venv active:

```bash
uvicorn main:app --reload --port 8000
```

It serves `http://localhost:8000`, with interactive docs at `/docs`.

| Route | Purpose |
|---|---|
| `GET /api/health` | status, model, whether a key is configured |
| `GET /api/tickets`, `GET /api/tickets/{id}` | tickets with open/resolved status and the latest proposal |
| `POST /api/tickets/{id}/run` | run the agent team on an open ticket (uses Portkey) |
| `GET /api/events` | agent activity from the audit trail |
| `POST /api/approvals` | a human approves one proposed payment or purchase |
| `POST /api/tickets/{id}/resolve` | a human approves a ticket's latest proposed resolution (no money moves) |
| `GET /api/cash` | checking balance |
| `POST /api/reset` | restore the working DB from the original (requires `{"confirm": true}`) |

## 5. Start the React dashboard

From `Homework-5/frontend/`:

```bash
npm run dev
```

Open **http://localhost:5173**, using `localhost` rather than `127.0.0.1`. If port 5173 is taken, Vite picks the next free port; the backend allows 5173–5179.

## 6. Prepare a clean database for a fresh three-ticket run

The working copy `data/campus_customs_new.db` currently holds the **completed Problem 9 state**:
- checking $1,000.00;
- one $2,400.00 rent payment;
- tickets #101–#103 resolved;
- invoice 501 open.

Resetting replaces that state with the original values. The original `data/campus_customs.db` is only read. Choose one method:

- **Dashboard:** *Desk tools* (⋯) → *Reset working database…* → type `RESET`.
- **API**, with the backend running:

  ```bash
  curl -X POST http://localhost:8000/api/reset -H "Content-Type: application/json" -d '{"confirm": true}'
  ```

- **Manually**, with the backend stopped, from `Homework-5/`:

  ```bash
  cp data/campus_customs.db data/campus_customs_new.db
  ```

What happens to the other records:
- `output/audit_trail.json` is append-only; a reset is recorded in it and nothing is deleted.
- `output/proposed_resolutions.json` keeps the last proposal per ticket until a new run replaces it.

To run the three tickets after a reset:
1. In the dashboard, select each ticket and press **Run the agent team**.
2. Review the proposal.
3. Approve any payment or purchase, and/or approve the resolution.

Each run makes real gpt-6-luna calls through Portkey (about 12–20 per ticket). The command-line alternative, from `Homework-5/`, runs all open tickets and only writes proposals:

```bash
python -m backend.run_tickets --all
```

## 7. Tests and checks (no Portkey calls)

From `Homework-5/` with the venv active:

```bash
python -m pytest -q
```

From `Homework-5/frontend/`:

```bash
npm run typecheck && npm run lint && npm test && npm run build
```

- **Backend tests** run against a temporary copy of the original database and temporary audit/proposal files, with scripted models in place of gpt-6-luna. They never touch the working database.
- **Frontend tests** use a mocked backend.

## Results (Problem 9)

All three tickets were resolved with human approval. Checking went **$3,400.00 → $1,000.00** (one $2,400.00 rent payment), using 41 model requests.

Known limitations (details in `output/harness.md`):
- #101 was closed **without paying overdue invoice 501** ($840, still open).
- #103's restock was **blocked because it had no cost**; a prompt change attempted before the run did not fix this.
- The Boss agent sometimes sends duplicate requests.
- Approvers are not authenticated.

Outcomes: `output/resolved_tickets.json`, `output/resolved_board.html`, and the Actual / Cash / Reflection tabs of `output/desk_tickets.html`.
