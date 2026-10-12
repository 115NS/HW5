"""Code-level shop-rule checks applied to every Boss proposal.

The prompts tell the agents the rules; these checks enforce them regardless of
what the model wrote. Cash checks go through the MCP `project_cash_balance`
tool, so they use the same data path as the agents.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .models import CONSEQUENTIAL_KINDS, BossProposal, RuleCheck, TicketResolution

# Kinds whose `amount` is money leaving the shop's cash account.
CASH_OUTFLOW_KINDS = {"payment", "restock_order"}

CallMcp = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


async def apply_guardrails(
    proposal: BossProposal,
    *,
    ticket_id: int,
    call_mcp: CallMcp,
    prior_outflows: list[dict[str, Any]] | None = None,
) -> tuple[TicketResolution, list[dict[str, Any]]]:
    """Check a proposal against the shop rules.

    `prior_outflows` are payments already proposed for earlier tickets in the
    same batch. None of them is paid, so a human approving everything would
    need cash for all of them; they are projected first.
    Returns the checked resolution and the cash outflows it adds.
    """
    prior_outflows = list(prior_outflows or [])
    checks: list[RuleCheck] = []
    actions = [a.model_copy() for a in proposal.proposed_actions]

    # 1. The proposal is for the ticket that was asked about.
    checks.append(
        RuleCheck(
            rule="Proposal is for the requested ticket",
            passed=proposal.ticket_id == ticket_id,
            detail=f"requested #{ticket_id}, proposal says #{proposal.ticket_id}",
        )
    )

    # 2. Payments and other consequential actions need a human.
    consequential = [a for a in actions if a.kind in CONSEQUENTIAL_KINDS]
    checks.append(
        RuleCheck(
            rule="Payments and other consequential actions require human approval",
            passed=all(a.requires_human_approval for a in consequential),
            detail=f"{len(consequential)} consequential action(s); all marked requires_human_approval and status 'proposed'. Nothing was executed.",
        )
    )

    # 3. Cash never goes negative, counting earlier proposals in this batch.
    new_outflows: list[dict[str, Any]] = []
    outflow_actions = [a for a in actions if a.kind in CASH_OUTFLOW_KINDS]
    for a in outflow_actions:
        if a.amount is None or a.amount <= 0:
            a.status = "blocked_by_guardrail"
            checks.append(
                RuleCheck(
                    rule="Cash outflows have a verifiable amount",
                    passed=False,
                    detail=f"Blocked '{a.description}': no positive amount, so the cash rule can't be checked.",
                )
            )
        else:
            new_outflows.append({"label": f"#{ticket_id} {a.kind}: {a.ref or a.description}"[:120], "amount": a.amount})

    if new_outflows:
        projection = await call_mcp("project_cash_balance", {"outflows": prior_outflows + new_outflows})
        if not projection.get("found", False):
            for a in outflow_actions:
                a.status = "blocked_by_guardrail"
            checks.append(RuleCheck(rule="Cash must never go negative", passed=False, detail=str(projection.get("error"))))
            new_outflows = []
        else:
            ok = projection["stays_non_negative"]
            if not ok:
                # Block this ticket's outflows from the first one that goes negative.
                steps = projection["steps"][len(prior_outflows):]
                negative_from = next((i for i, s in enumerate(steps) if s["balance_after"] < 0), 0)
                verified = [a for a in outflow_actions if a.status == "proposed"]
                for a in verified[negative_from:]:
                    a.status = "blocked_by_guardrail"
                new_outflows = new_outflows[:negative_from]
            checks.append(
                RuleCheck(
                    rule="Cash must never go negative",
                    passed=ok,
                    detail=(
                        f"Projected via MCP project_cash_balance: start ${projection['starting_balance']:,.2f}, "
                        f"outflows ${projection['total_outflows']:,.2f} (incl. {len(prior_outflows)} earlier batch proposal(s)), "
                        f"end ${projection['ending_balance']:,.2f}."
                        + ("" if ok else f" First negative: {projection['first_negative']}; those payments are blocked.")
                    ),
                )
            )
    else:
        checks.append(RuleCheck(rule="Cash must never go negative", passed=True, detail="No cash outflow proposed for this ticket."))

    # 4. Nobody outside the shop is contacted.
    draft = proposal.customer_reply_draft
    checks.append(
        RuleCheck(
            rule="No real customers or vendors are contacted",
            passed=draft is None or draft.sent is False,
            detail="The system has no send, email, or ordering tools; "
            + ("the customer reply is a draft (sent=false)." if draft else "no customer reply was drafted."),
        )
    )

    if any(a.status == "proposed" and a.requires_human_approval for a in actions):
        approval_status = "pending_human_approval"
    elif any(a.status == "blocked_by_guardrail" for a in actions):
        approval_status = "blocked_by_guardrail"
    else:
        approval_status = "no_approval_needed"

    data = proposal.model_dump()
    data.update(ticket_id=ticket_id, proposed_actions=[a.model_dump() for a in actions])
    resolution = TicketResolution(**data, rule_checks=checks, approval_status=approval_status)
    return resolution, new_outflows
