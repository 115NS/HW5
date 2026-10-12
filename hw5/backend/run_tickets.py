"""Resolve Campus Customs tickets with the agent team (live: gpt-6-luna via Portkey).

From Homework/Homework-5, with the HW5 venv active:

    python -m backend.run_tickets --ticket 101
    python -m backend.run_tickets --ticket 101 --ticket 102 --ticket 103
    python -m backend.run_tickets --all          # every open ticket

Each run makes real Portkey calls. Proposals are printed and saved to
output/proposed_resolutions.json; every step is appended to
output/audit_trail.json. Nothing is paid, ordered, or sent.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from . import proposals
from .agents import HW5_DIR, Team


async def main(ticket_ids: list[int], run_all: bool) -> None:
    out_path = HW5_DIR / "output" / "proposed_resolutions.json"
    async with Team() as team:
        if run_all:
            queue = await team.mcp.direct_call_tool("list_open_tickets", {})
            ticket_ids = [t["id"] for t in queue["tickets"]]
        for ticket_id in ticket_ids:
            # One ticket failing (already audited as run_end/failed) must not stop the others.
            try:
                resolution = await team.resolve(ticket_id)
            except Exception as exc:
                proposals.save(out_path, ticket_id, {"ticket_id": ticket_id, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})
                print(f"Ticket #{ticket_id} failed: {type(exc).__name__}: {exc}")
            else:
                proposals.save(out_path, ticket_id, resolution.model_dump())
                print(json.dumps(resolution.model_dump(), indent=2))
    ok, problems = team.audit.verify()
    print(f"\nAudit trail: {len(team.audit.entries())} entries, chain {'intact' if ok else 'BROKEN: ' + '; '.join(problems)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Propose resolutions for Campus Customs tickets (no actions executed).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", type=int, action="append", help="ticket id; repeat for several")
    group.add_argument("--all", action="store_true", help="every open ticket")
    args = parser.parse_args()
    asyncio.run(main(args.ticket or [], args.all))
