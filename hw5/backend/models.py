"""Data types shared by the Campus Customs agent team (Homework 5, Problem 5).

The Literal-typed fields encode shop rules in the schema itself: a proposed
action can never be marked executed or approved by an agent, and a customer
reply can never be marked sent.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
SpecialistName = Literal["inventory", "accounting", "facilities", "customer_service"]

ActionKind = Literal[
    "payment",           # money leaving the shop (rent, vendor invoice)
    "restock_order",     # buying stock from a vendor
    "discount_offer",    # pricing below list
    "customer_reply",    # a message to a customer (draft only)
    "substitute_offer",  # offering another size or item
    "hold",              # wait / do nothing yet
    "escalate",          # needs a human decision outside the agents' scope
    "other",
]

# Anything that spends money, commits the shop, or reaches a real person.
CONSEQUENTIAL_KINDS: frozenset[str] = frozenset(
    {"payment", "restock_order", "discount_offer", "customer_reply", "substitute_offer"}
)


class Fact(BaseModel):
    """One shop fact, with where it came from, so nothing is invented."""

    label: str = Field(description="Short name, e.g. 'CC-TEE-WHITE S on hand'.")
    value: str = Field(description="The value exactly as returned, e.g. '0' or '$2,400.00 due 2026-09-02'.")
    source: str = Field(description="MCP tool (e.g. 'check_stock') or agent (e.g. 'inventory') that supplied it.")


class ProposedAction(BaseModel):
    """Something a human could choose to do. Agents only ever propose."""

    kind: ActionKind
    description: str
    amount: float | None = Field(default=None, description="Dollars, for payments, orders, and discounts.")
    payee: str | None = Field(default=None, description="Who would be paid or contacted, if anyone.")
    ref: str | None = Field(default=None, description="Record it relates to, e.g. 'lease 1' or 'invoice 501'.")
    requires_human_approval: bool = True
    status: Literal["proposed", "blocked_by_guardrail"] = "proposed"

    @model_validator(mode="after")
    def _consequential_needs_approval(self) -> ProposedAction:
        if self.kind in CONSEQUENTIAL_KINDS:
            self.requires_human_approval = True
        return self


class SpecialistReport(BaseModel):
    """What a specialist hands back to whoever delegated to it."""

    agent: SpecialistName
    ticket_id: int
    summary: str = Field(description="Two or three sentences answering the task you were given.")
    facts: list[Fact] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    concerns: list[str] = Field(
        default_factory=list, description="Rule risks, missing data, or anything the Boss must decide."
    )


class CustomerReplyDraft(BaseModel):
    """A reply for a human to review. It is never sent by the system."""

    to: str
    subject: str
    body: str
    sent: Literal[False] = False
    note: Literal["Draft only. Not sent. A human must review and send it."] = (
        "Draft only. Not sent. A human must review and send it."
    )


class BossProposal(BaseModel):
    """The Boss agent's structured output for one ticket."""

    ticket_id: int
    ticket_type: str
    summary: str = Field(description="What the ticket needs and what the team found, in plain language.")
    delegated_to: list[SpecialistName] = Field(default_factory=list)
    key_facts: list[Fact] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list, description="Every realistic option, including 'wait'.")
    recommended_option: str
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    customer_reply_draft: CustomerReplyDraft | None = None
    open_questions: list[str] = Field(default_factory=list)


class RuleCheck(BaseModel):
    rule: str
    passed: bool
    detail: str


class TicketResolution(BossProposal):
    """The Boss proposal after the code-level guardrails have checked it."""

    rule_checks: list[RuleCheck] = Field(default_factory=list)
    approval_status: Literal["pending_human_approval", "no_approval_needed", "blocked_by_guardrail"]
    run_id: str | None = Field(default=None, description="Audit-trail run that produced this proposal.")
