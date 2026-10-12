"""Shop rules enforced in code, independent of what a model writes."""

import asyncio

import pytest
from fastmcp import Client
from pydantic import ValidationError

from backend.guardrails import apply_guardrails
from backend.models import BossProposal, CustomerReplyDraft, ProposedAction
from server import mcp


async def call_mcp(name, args):
    async with Client(mcp) as c:
        return (await c.call_tool(name, args)).data


def proposal(*actions, draft=None, ticket_id=102):
    return BossProposal(ticket_id=ticket_id, ticket_type="rent_notice", summary="s", recommended_option="r",
                        proposed_actions=list(actions), customer_reply_draft=draft)


def check(p, ticket_id=102, prior=None):
    return asyncio.run(apply_guardrails(p, ticket_id=ticket_id, call_mcp=call_mcp, prior_outflows=prior))


def rent(amount=2400.0):
    return ProposedAction(kind="payment", description="Pay rent", amount=amount, payee="Elm City Properties", ref="lease 1")


def test_affordable_payment_is_pending_human_approval():
    res, outflows = check(proposal(rent()))
    assert res.approval_status == "pending_human_approval"
    assert res.proposed_actions[0].status == "proposed" and res.proposed_actions[0].requires_human_approval
    assert all(c.passed for c in res.rule_checks)
    assert outflows == [{"label": "#102 payment: lease 1", "amount": 2400.0}]


def test_payment_that_would_overdraw_is_blocked():
    res, outflows = check(proposal(rent(), rent(1500.0)))
    assert [a.status for a in res.proposed_actions] == ["proposed", "blocked_by_guardrail"]
    cash = next(c for c in res.rule_checks if c.rule == "Cash must never go negative")
    assert cash.passed is False and "end $-500.00" in cash.detail
    assert len(outflows) == 1


def test_earlier_batch_proposals_count_against_cash():
    res, _ = check(proposal(rent()), prior=[{"label": "#101 payment: invoice 501", "amount": 1500.0}])
    assert res.proposed_actions[0].status == "blocked_by_guardrail"
    assert res.approval_status == "blocked_by_guardrail"


def test_payment_without_amount_is_blocked():
    res, _ = check(proposal(ProposedAction(kind="payment", description="Pay something")))
    assert res.proposed_actions[0].status == "blocked_by_guardrail"


def test_wrong_ticket_id_is_flagged_and_corrected():
    res, _ = check(proposal(ticket_id=999), ticket_id=102)
    assert res.ticket_id == 102 and res.rule_checks[0].passed is False


def test_consequential_actions_always_need_approval():
    a = ProposedAction(kind="discount_offer", description="10% off", requires_human_approval=False)
    assert a.requires_human_approval is True
    assert ProposedAction(kind="hold", description="wait", requires_human_approval=False).requires_human_approval is False


def test_schema_forbids_executed_actions_and_sent_replies():
    with pytest.raises(ValidationError):
        ProposedAction(kind="payment", description="x", amount=1, status="executed")
    with pytest.raises(ValidationError):
        CustomerReplyDraft(to="a", subject="b", body="c", sent=True)
