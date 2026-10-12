"""Campus Customs dashboard API (Homework 5, Problem 7).

Run from the backend/ folder:

    uvicorn main:app --reload --port 8000      # http://localhost:8000  (docs at /docs)

Reads go through the campus-customs MCP server; agent runs use the existing
PydanticAI team (gpt-6-luna via Portkey). Agents only propose. The only writes
to the working database are a human's explicit approval of a proposed payment
or purchase, and a reset to the original values (backend/ledger.py). The
original data/campus_customs.db is never written.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import uuid4

# `uvicorn main:app` runs from backend/, so make the Homework-5 root importable for the `backend` package.
HW5_DIR = Path(__file__).resolve().parents[1]
if str(HW5_DIR) not in sys.path:
    sys.path.insert(0, str(HW5_DIR))
if str(HW5_DIR / "mcp_server") not in sys.path:
    sys.path.insert(0, str(HW5_DIR / "mcp_server"))

from fastapi import FastAPI, HTTPException, Path as PathParam, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field, field_validator  # noqa: E402

import server as mcp_server  # noqa: E402  (mcp_server/server.py, used in-process over MCP)
from backend import ledger, proposals  # noqa: E402
from backend.agents import AGENTS, AUDIT_PATH, MODEL_NAME, AgentNotConfigured, Team, build_model  # noqa: E402
from backend.audit import AuditTrail  # noqa: E402

PROPOSALS_PATH = HW5_DIR / "output" / "proposed_resolutions.json"
TicketId = Annotated[int, PathParam(gt=0, le=1_000_000, description="Ticket id, e.g. 101")]


# --- settings and state ------------------------------------------------------


@dataclass
class Settings:
    audit_path: Path = AUDIT_PATH
    proposals_path: Path = PROPOSALS_PATH
    # Returns the model(s) for a run. Default: gpt-6-luna via Portkey. Tests pass scripted models.
    models_factory: Callable[[], Any] = build_model
    # The Vite dev server (Problem 8): http://localhost:5173, or the next free port Vite falls back to (5174-5179)
    # when 5173 is taken. Local origins only. CORS limits which pages may call the API; it is not authentication.
    cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1):517[3-9]$"


@dataclass
class RunInfo:
    ticket_id: int
    status: Literal["running", "completed", "failed"]
    started_at: str
    finished_at: str | None = None
    run_id: str | None = None
    error: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def call_mcp(name: str, args: dict[str, Any] | None = None) -> Any:
    """Call a campus-customs MCP tool in-process (same server and data path as the agents)."""
    async with Client(mcp_server.mcp) as client:
        return (await client.call_tool(name, args or {})).data


# --- request bodies ------------------------------------------------------------


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wait: bool = Field(False, description="true: wait for the run and return the proposal; false: start it and return 202.")


class ApprovalRequest(BaseModel):
    """A human's explicit approval of one proposed payment or purchase."""

    model_config = ConfigDict(extra="forbid")
    ticket_id: int = Field(gt=0, le=1_000_000)
    action_id: str = Field(pattern=r"^[0-9a-f]{6,32}:\d{1,3}$", description="From GET /api/tickets/{id}: '<run_id>:<index>'.")
    amount: float = Field(gt=0, le=1_000_000, description="Must equal the proposed amount exactly.")
    approved_by: str = Field(min_length=2, max_length=80, description="Name of the human approving.")
    confirm: Literal[True] = Field(description="Must be true: the human confirms this payment.")
    resolve_ticket: bool = Field(True, description="Mark the ticket resolved after the payment is recorded.")

    @field_validator("approved_by")
    @classmethod
    def _human_name(cls, v: str) -> str:
        v = " ".join(v.split())
        if v.lower().replace(" ", "_") in {*AGENTS, "agent", "system", "guardrails", "ai", "bot"}:
            raise ValueError("approved_by must be the human approving, not an agent or system name.")
        return v


class ResolveRequest(BaseModel):
    """A human's explicit approval of a ticket's proposed resolution. Moves no money."""

    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(pattern=r"^[0-9a-f]{6,32}$", description="The run whose proposal is being approved (must be the latest).")
    approved_by: str = Field(min_length=2, max_length=80, description="Name of the human approving.")
    confirm: Literal[True] = Field(description="Must be true: the human approves resolving the ticket as proposed.")
    acknowledge_unpaid: bool = Field(False, description="Required if approvable payments/purchases are still pending: they will be left unpaid.")
    note: str | None = Field(None, max_length=500)

    _human_name = field_validator("approved_by")(ApprovalRequest._human_name.__func__)


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True] = Field(description="Must be true: reset the working database to the original values.")


# --- app -----------------------------------------------------------------------


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.audit = AuditTrail(settings.audit_path)
        app.state.runs: dict[int, RunInfo] = {}
        app.state.tasks: set[asyncio.Task] = set()
        app.state.run_lock = asyncio.Lock()  # one agent run at a time (shared budget, consistent cash view)
        app.state.write_lock = asyncio.Lock()  # approvals and resets are serialized
        yield
        for task in app.state.tasks:
            task.cancel()

    app = FastAPI(title="Campus Customs Desk API", version="1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origin_regex=settings.cors_origin_regex, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "Accept"])

    @app.exception_handler(ledger.LedgerError)
    async def _ledger_error(_: Request, exc: ledger.LedgerError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    @app.exception_handler(ToolError)
    async def _tool_error(_: Request, exc: ToolError):
        return JSONResponse(status_code=422, content={"detail": f"MCP tool rejected the request: {exc}"})

    # -- helpers --

    def audit(request: Request) -> AuditTrail:
        return request.app.state.audit

    async def get_ticket_or_404(ticket_id: int) -> dict[str, Any]:
        res = await call_mcp("get_ticket", {"ticket_id": ticket_id})
        if not res.get("found"):
            raise HTTPException(404, f"Ticket {ticket_id} not found.")
        return res["ticket"]

    def proposal_view(request: Request, ticket_id: int) -> dict[str, Any] | None:
        record = proposals.load(settings.proposals_path).get(str(ticket_id))
        if record is None:
            return None
        if record.get("status") == "failed":
            return record
        return proposals.with_action_ids(record, ticket_id, audit(request).entries())

    def run_view(request: Request, ticket_id: int) -> dict[str, Any] | None:
        info = request.app.state.runs.get(ticket_id)
        return vars(info) if info else None

    def reject(request: Request, body: ApprovalRequest, status: int, detail: str):
        """Record a refused approval in the audit trail, then return the error."""
        audit(request).append(action="human_approval_rejected", run_id=f"human-{uuid4().hex[:8]}", ticket_id=body.ticket_id,
                              agent="human", error=detail, details={"action_id": body.action_id, "amount": body.amount,
                                                                     "approved_by": body.approved_by, "http_status": status})
        raise HTTPException(status, detail)

    async def run_ticket(app_: FastAPI, ticket_id: int, models: Any) -> dict[str, Any]:
        info: RunInfo = app_.state.runs[ticket_id]
        try:
            async with Team(models, audit_path=settings.audit_path) as team:
                # Unapproved payments proposed for other tickets still compete for the same cash.
                team.batch_outflows = proposals.pending_outflows(settings.proposals_path, team.audit.entries(), exclude_ticket=ticket_id)
                resolution = await team.resolve(ticket_id)
            record = resolution.model_dump()
            proposals.save(settings.proposals_path, ticket_id, record)
            info.status, info.run_id = "completed", resolution.run_id
            return record
        except Exception as exc:
            info.status, info.error = "failed", f"{type(exc).__name__}: {exc}"
            raise
        finally:
            info.finished_at = _now()

    # -- routes --

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        """Service status; never returns the API key itself."""
        return {"status": "ok", "model": MODEL_NAME, "portkey_key_configured": bool(os.environ.get("PORTKEY_API_KEY")),
                "database": ledger.working_db().name}

    @app.get("/api/tickets")
    async def list_tickets(request: Request) -> dict[str, Any]:
        """All tickets with open/resolved status, plus each one's latest run and proposal state."""
        res = await call_mcp("list_tickets")
        tickets = []
        for t in res["tickets"]:
            prop = proposal_view(request, t["id"])
            actions = (prop or {}).get("proposed_actions", [])
            tickets.append({
                **t,
                "status": "resolved" if t["status"] == "resolved" else "open",
                "run": run_view(request, t["id"]),
                "proposal": None if prop is None else {
                    "run_id": prop.get("run_id"),
                    "approval_status": prop.get("approval_status", prop.get("status")),
                    "summary": prop.get("summary") or prop.get("error"),
                    "approvable_actions": sum(1 for a in actions if a.get("approvable")),
                },
            })
        return {"desk_date": res["desk_date"], "count": len(tickets), "tickets": tickets}

    @app.get("/api/tickets/{ticket_id}")
    async def get_ticket(request: Request, ticket_id: TicketId) -> dict[str, Any]:
        """One ticket, its latest run status, and its full proposal with action ids and approval state."""
        ticket = await get_ticket_or_404(ticket_id)
        return {"ticket": {**ticket, "status": "resolved" if ticket["status"] == "resolved" else "open"},
                "run": run_view(request, ticket_id), "proposal": proposal_view(request, ticket_id)}

    @app.post("/api/tickets/{ticket_id}/run", status_code=202)
    async def run_agents(request: Request, ticket_id: TicketId, body: RunRequest | None = None):
        """Run the existing agent team on one open ticket. Produces a proposal only; nothing is executed."""
        body = body or RunRequest()
        ticket = await get_ticket_or_404(ticket_id)
        if ticket["status"] != "open":
            raise HTTPException(409, f"Ticket {ticket_id} is {ticket['status']}; only open tickets can be run.")
        state = request.app.state
        if state.run_lock.locked():
            busy = next((i.ticket_id for i in state.runs.values() if i.status == "running"), None)
            raise HTTPException(409, f"An agent run is already in progress (ticket {busy}). Try again when it finishes.")
        try:
            models = settings.models_factory()
        except AgentNotConfigured as exc:
            raise HTTPException(503, str(exc)) from None

        await state.run_lock.acquire()
        state.runs[ticket_id] = RunInfo(ticket_id=ticket_id, status="running", started_at=_now())

        async def job() -> dict[str, Any]:
            try:
                return await run_ticket(request.app, ticket_id, models)
            finally:
                state.run_lock.release()

        if body.wait:
            try:
                record = await job()
            except Exception:
                raise HTTPException(502, f"Agent run failed: {state.runs[ticket_id].error}") from None
            return JSONResponse(status_code=200, content={"run": run_view(request, ticket_id),
                                                         "proposal": proposal_view(request, ticket_id) or record})
        task = asyncio.create_task(job())
        state.tasks.add(task)
        task.add_done_callback(lambda t: (state.tasks.discard(t), t.cancelled() or t.exception()))
        return {"run": run_view(request, ticket_id), "poll": [f"/api/tickets/{ticket_id}", f"/api/events?ticket_id={ticket_id}"]}

    @app.get("/api/events")
    async def events(
        request: Request,
        ticket_id: int | None = Query(None, gt=0, le=1_000_000),
        after_seq: int = Query(-1, ge=-1, description="Only events with seq greater than this (for polling)."),
        limit: int = Query(50, ge=1, le=500),
    ) -> dict[str, Any]:
        """Recent agent events from the audit trail: what each agent said, delegations, and tool calls."""
        entries = [e for e in audit(request).entries() if e["seq"] > after_seq and (ticket_id is None or e["ticket_id"] == ticket_id)]
        entries = entries[-limit:]
        return {"count": len(entries), "last_seq": entries[-1]["seq"] if entries else after_seq,
                "events": [_event_view(e) for e in entries]}

    @app.post("/api/approvals")
    async def approve(request: Request, body: ApprovalRequest) -> dict[str, Any]:
        """A human approves one proposed payment or purchase; this records it and updates checking."""
        async with request.app.state.write_lock:
            ticket = await get_ticket_or_404(body.ticket_id)
            prop = proposal_view(request, body.ticket_id)
            if prop is None or prop.get("status") == "failed":
                reject(request, body, 404, f"No proposal for ticket {body.ticket_id}; run the agents first.")
            action = next((a for a in prop["proposed_actions"] if a["action_id"] == body.action_id), None)
            if action is None:
                reject(request, body, 409 if body.action_id.split(":")[0] != prop.get("run_id") else 404,
                       f"Action {body.action_id} is not in ticket {body.ticket_id}'s latest proposal (run {prop.get('run_id')}).")
            if action["kind"] not in proposals.PAYABLE_KINDS:
                reject(request, body, 422, f"Only payments and purchases can be approved here; this action is a {action['kind']}.")
            if action["status"] != "proposed":
                reject(request, body, 409, f"This action was {action['status']}; it can't be approved.")
            if action["approval"]:
                reject(request, body, 409, f"Already approved by {action['approval']['approved_by']} (payment {action['approval']['payment_id']}).")
            if not action.get("amount") or abs(action["amount"] - body.amount) > 0.005:
                reject(request, body, 409, f"Amount ${body.amount:,.2f} does not match the proposed ${action.get('amount') or 0:,.2f}.")

            kind, ref_id = await _payment_target(body, ticket, action, lambda s, d: reject(request, body, s, d))

            projection = await call_mcp("project_cash_balance", {"outflows": [{"label": f"#{body.ticket_id} {kind}", "amount": body.amount}]})
            if not projection["stays_non_negative"]:
                reject(request, body, 409, f"Insufficient cash: checking has ${projection['starting_balance']:,.2f}; "
                                           f"this would leave ${projection['ending_balance']:,.2f}.")
            try:
                result = ledger.execute_approved_payment(kind=kind, ref_id=ref_id, amount=body.amount, approved_by=body.approved_by,
                                                         ticket_id=body.ticket_id, resolve_ticket=body.resolve_ticket)
            except ledger.LedgerError as exc:
                reject(request, body, exc.status, exc.detail)

            details = {"action_id": body.action_id, "action_kind": action["kind"], "description": action["description"],
                       "payment_id": result.payment_id, "payment_kind": kind, "ref_id": ref_id, "amount": body.amount,
                       "approved_by": body.approved_by, "balance_before": result.balance_before,
                       "balance_after": result.balance_after, "ticket_status": result.ticket_status}
            audit(request).append(action="human_approval", run_id=f"human-{uuid4().hex[:8]}", ticket_id=body.ticket_id,
                                  agent="human", approval_status="approved", details=details)
            return {"approved": True, **details, "paid_at": result.paid_at}

    @app.post("/api/tickets/{ticket_id}/resolve")
    async def resolve(request: Request, ticket_id: TicketId, body: ResolveRequest) -> dict[str, Any]:
        """A human approves the latest proposed resolution and marks the ticket resolved. No money moves."""
        state = request.app.state
        async with state.write_lock:
            ticket = await get_ticket_or_404(ticket_id)

            def refuse(status: int, detail: str):
                audit(request).append(action="human_resolution_rejected", run_id=f"human-{uuid4().hex[:8]}", ticket_id=ticket_id,
                                      agent="human", error=detail, details={"proposal_run_id": body.run_id,
                                                                             "approved_by": body.approved_by, "http_status": status})
                raise HTTPException(status, detail)

            if ticket["status"] != "open":
                refuse(409, f"Ticket {ticket_id} is already {ticket['status']}.")
            if state.runs.get(ticket_id) and state.runs[ticket_id].status == "running":
                refuse(409, f"An agent run for ticket {ticket_id} is in progress; wait for its proposal.")
            prop = proposal_view(request, ticket_id)
            if prop is None or prop.get("status") == "failed":
                refuse(404, f"No proposal for ticket {ticket_id}; run the agents first.")
            if prop.get("run_id") != body.run_id:
                refuse(409, f"Run {body.run_id} is not ticket {ticket_id}'s latest proposal (run {prop.get('run_id')}).")
            actions = prop["proposed_actions"]
            pending = [a for a in actions if a["approvable"]]
            if pending and not body.acknowledge_unpaid:
                refuse(409, f"{len(pending)} payment(s)/purchase(s) are still awaiting approval. Approve them first, "
                            "or set acknowledge_unpaid to resolve without paying them.")
            status = ledger.resolve_ticket(ticket_id)
            details = {
                "proposal_run_id": body.run_id, "approved_by": body.approved_by, "note": body.note,
                "recommended_option": prop.get("recommended_option"),
                "paid": [{"action_id": a["action_id"], "amount": a["amount"], "payment_id": a["approval"]["payment_id"]}
                         for a in actions if a.get("approval")],
                "left_unpaid": [{"action_id": a["action_id"], "kind": a["kind"], "amount": a["amount"], "description": a["description"]}
                                for a in pending],
                "ticket_status": status,
            }
            audit(request).append(action="human_resolution", run_id=f"human-{uuid4().hex[:8]}", ticket_id=ticket_id,
                                  agent="human", approval_status="resolved", details=details)
            return {"resolved": True, "ticket_id": ticket_id, **details}

    @app.get("/api/cash")
    async def cash() -> dict[str, Any]:
        """Current checking balance from cash_accounts (via MCP)."""
        res = await call_mcp("get_cash_position")
        checking = next((a for a in res["accounts"] if a["account"] == "checking"), None)
        if checking is None:
            raise HTTPException(404, "No checking account in cash_accounts.")
        return {"account": "checking", "balance": checking["balance"], "as_of": checking["as_of"], "desk_date": res["desk_date"]}

    @app.post("/api/reset")
    async def reset(request: Request, body: ResetRequest) -> dict[str, Any]:
        """Reset the working database to the original values. The original file is only read."""
        if request.app.state.run_lock.locked():
            raise HTTPException(409, "An agent run is in progress; reset after it finishes.")
        async with request.app.state.write_lock:
            digest = ledger.reset_working_db()
            audit(request).append(action="database_reset", run_id=f"reset-{uuid4().hex[:8]}", ticket_id=None, agent="human",
                                  details={"database": ledger.working_db().name, "sha256": digest,
                                           "note": "Working copy restored from data/campus_customs.db; earlier approvals no longer apply."})
        request.app.state.runs.clear()
        return {"reset": True, "sha256": digest, "cash": await cash(), "tickets": (await call_mcp("list_tickets"))["count"]}

    return app


async def _payment_target(body: ApprovalRequest, ticket: dict[str, Any], action: dict[str, Any], reject) -> tuple[str, int | None]:
    """Work out what a proposed action pays for, and check it against the database (via MCP)."""
    if action["kind"] == "restock_order":
        return "purchase", body.ticket_id

    text = " ".join(str(action.get(k) or "") for k in ("ref", "description", "payee")).lower()
    inv = re.search(r"invoice\s*#?\s*(\d+)", text)
    lease = re.search(r"lease\s*#?\s*(\d+)", text)
    invoice_id = int(inv.group(1)) if inv else (ticket["invoice_id"] if "invoice" in text else None)
    lease_id = int(lease.group(1)) if lease else (ticket["lease_id"] if re.search(r"\b(rent|lease)\b", text) else None)

    if invoice_id is not None:
        if invoice_id != ticket["invoice_id"]:
            reject(409, f"Invoice {invoice_id} is not linked to ticket {body.ticket_id}.")
        res = await call_mcp("get_invoice", {"invoice_id": invoice_id})
        if not res.get("found"):
            reject(404, f"Invoice {invoice_id} not found.")
        inv_rec = res["invoice"]
        if inv_rec["status"] != "open":
            reject(409, f"Invoice {invoice_id} is already {inv_rec['status']}.")
        if abs(inv_rec["amount"] - body.amount) > 0.005:
            reject(409, f"Invoice {invoice_id} is ${inv_rec['amount']:,.2f}; the proposal says ${body.amount:,.2f}.")
        return "invoice", invoice_id

    if lease_id is not None:
        if lease_id != ticket["lease_id"]:
            reject(409, f"Lease {lease_id} is not linked to ticket {body.ticket_id}.")
        rent = await call_mcp("get_rent_due", {"lease_id": lease_id})
        if not rent.get("found"):
            reject(404, f"Lease {lease_id} not found.")
        if abs(rent["monthly_rent"] - body.amount) > 0.005:
            reject(409, f"Rent on lease {lease_id} is ${rent['monthly_rent']:,.2f}; the proposal says ${body.amount:,.2f}.")
        paid = await call_mcp("list_payments", {"kind": "rent", "ref_id": lease_id})
        if paid["count"]:
            reject(409, f"Rent for lease {lease_id} is already paid.")
        return "rent", lease_id

    reject(422, "Can't tell what this payment is for (no linked invoice or lease); it can't be approved here.")
    raise AssertionError  # reject always raises


def _event_view(e: dict[str, Any]) -> dict[str, Any]:
    """Shape one audit entry for the dashboard: who, what they said, which tool."""
    d = e.get("details") or {}
    tool = e.get("tool")
    deleg = e.get("delegation")
    a = e["action"]
    if a == "run_start":
        msg = f"Run started on {', '.join(d.get('models', []))}"
    elif a == "agent_start":
        msg = d.get("prompt", "")
    elif a == "model_step":
        calls = ", ".join(c["tool"] for c in d.get("requested_calls", []))
        msg = d.get("text") or (f"Decided to call: {calls}" if calls else "Thinking")
    elif a == "tool_call":
        msg = f"Called {tool['name']}"
    elif a == "tool_result":
        msg = f"{tool['name']} returned"
    elif a in ("delegation_request",):
        msg = f"Asked {deleg['to']}: {deleg['task']}"
    elif a == "delegation_result":
        msg = f"{deleg['to']} reported: {d.get('summary', '')}"
    elif a in ("delegation_blocked", "delegation_failed", "delegation_reused"):
        msg = f"{a.replace('_', ' ').capitalize()} ({deleg['to']}): {e.get('error') or 'returned the earlier answer'}"
    elif a == "agent_output":
        msg = d.get("summary", "")
    elif a == "guardrail_check":
        msg = f"{'PASS' if d.get('passed') else 'FAIL'}: {d.get('rule')}. {d.get('detail', '')}"
    elif a == "resolution":
        msg = f"Proposed resolution ({e.get('approval_status')}): {d.get('summary', '')}"
    elif a == "run_end":
        msg = f"Run {d.get('status', 'ended')}: {d.get('requests', '?')} model requests" + (f", error {e['error']}" if e.get("error") else "")
    elif a == "human_approval":
        msg = f"{d['approved_by']} approved ${d['amount']:,.2f} ({d['payment_kind']}); checking ${d['balance_before']:,.2f} → ${d['balance_after']:,.2f}"
    elif a == "human_approval_rejected":
        msg = f"Approval refused: {e.get('error')}"
    elif a == "human_resolution":
        unpaid = d.get("left_unpaid") or []
        msg = f"{d['approved_by']} approved the proposed resolution; ticket resolved" + (f" ({len(unpaid)} payable item(s) left unpaid)" if unpaid else "")
    elif a == "human_resolution_rejected":
        msg = f"Resolution refused: {e.get('error')}"
    elif a == "database_reset":
        msg = "Working database reset to the original values"
    else:
        msg = e.get("error") or a
    return {
        "seq": e["seq"], "ts": e["ts"], "run_id": e["run_id"], "ticket_id": e["ticket_id"], "agent": e["agent"], "action": a,
        "message": msg, "chain": e.get("chain"), "step": e.get("step"),
        "tool": {"name": tool["name"], "args": tool.get("args"), "result": tool.get("result")} if tool else None,
        "delegation": deleg, "approval_status": e.get("approval_status"), "error": e.get("error"),
    }


app = create_app()
