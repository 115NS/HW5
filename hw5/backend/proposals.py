"""Proposal store (output/proposed_resolutions.json), shared by the CLI and the API.

The file maps ticket id -> the latest TicketResolution for that ticket. Each
proposed action gets a stable id "<run_id>:<index>" so a human approval names
exactly one action from one agent run. Approval state is read from the audit
trail (human_approval entries since the last database_reset), so it can't be
edited separately from the audit record.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

PAYABLE_KINDS = ("payment", "restock_order")


def load(path: Path) -> dict[str, dict[str, Any]]:
    return json.loads(path.read_text()) if path.exists() else {}


def save(path: Path, ticket_id: int, resolution: dict[str, Any]) -> None:
    """Replace one ticket's latest proposal; other tickets are kept. Atomic write."""
    data = load(path)
    data[str(ticket_id)] = resolution
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".proposals-", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def run_id_for(record: dict[str, Any], ticket_id: int, audit_entries: list[dict[str, Any]]) -> str | None:
    """The run that produced a stored proposal. Older records (saved before run_id
    was stored) are matched to the latest `resolution` entry for that ticket."""
    if record.get("run_id"):
        return record["run_id"]
    runs = [e["run_id"] for e in audit_entries if e["action"] == "resolution" and e["ticket_id"] == ticket_id]
    return runs[-1] if runs else None


def approvals_since_reset(audit_entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """action_id -> approval entry details, counting only approvals after the last database reset."""
    approved: dict[str, dict[str, Any]] = {}
    for e in audit_entries:
        if e["action"] == "database_reset":
            approved.clear()
        elif e["action"] == "human_approval":
            approved[e["details"]["action_id"]] = {**e["details"], "seq": e["seq"], "ts": e["ts"]}
    return approved


def with_action_ids(record: dict[str, Any], ticket_id: int, audit_entries: list[dict[str, Any]]) -> dict[str, Any]:
    """A copy of the record with run_id, and each action's id and approval state."""
    run_id = run_id_for(record, ticket_id, audit_entries)
    approved = approvals_since_reset(audit_entries)
    actions = []
    for i, a in enumerate(record.get("proposed_actions", [])):
        action_id = f"{run_id}:{i}" if run_id else None
        approval = approved.get(action_id) if action_id else None
        payable = a["kind"] in PAYABLE_KINDS and a["status"] == "proposed" and (a.get("amount") or 0) > 0
        actions.append({
            **a,
            "action_id": action_id,
            "approval": approval,
            "approvable": bool(payable and action_id and approval is None),
        })
    return {**record, "run_id": run_id, "proposed_actions": actions}


def pending_outflows(path: Path, audit_entries: list[dict[str, Any]], *, exclude_ticket: int | None = None) -> list[dict[str, Any]]:
    """Unapproved payments/purchases proposed for other tickets. A new run's cash
    guardrail counts them, since a human could still approve all of them."""
    out = []
    for tid, record in load(path).items():
        if record.get("status") == "failed" or int(tid) == exclude_ticket:
            continue
        for a in with_action_ids(record, int(tid), audit_entries)["proposed_actions"]:
            if a["approvable"]:
                out.append({"label": f"#{tid} {a['kind']}: {a.get('ref') or a['description']}"[:120], "amount": a["amount"]})
    return out
