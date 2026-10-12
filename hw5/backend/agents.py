"""Campus Customs multi-agent team (Homework 5, Problem 5).

Five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer
Service) share one MCP connection to mcp_server/server.py, which reads
data/campus_customs_new.db. Each agent sees only its own MCP tools (see
AGENT_MCP_TOOLS) and may delegate only along DELEGATES. There is no separate
shop-tools layer: every shop fact comes through MCP.

Every agent-loop step is appended to output/audit_trail.json.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.messages import TextPart, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.usage import RunUsage, UsageLimits

from .audit import AuditTrail
from .guardrails import apply_guardrails
from .models import BossProposal, SpecialistReport, TicketResolution

HW5_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = HW5_DIR / "backend" / "prompts"
MCP_SERVER = HW5_DIR / "mcp_server" / "server.py"
AUDIT_PATH = HW5_DIR / "output" / "audit_trail.json"

MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# PORTKEY_API_KEY: an exported variable, Homework-5/.env, or the AI Foundations root .env.
# Existing variables are never overridden.
load_dotenv(HW5_DIR / ".env")
load_dotenv(HW5_DIR.parents[1] / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

AGENTS = ("boss", "inventory", "accounting", "facilities", "customer_service")

# Which MCP tools each agent may call.
AGENT_MCP_TOOLS: dict[str, frozenset[str]] = {
    "boss": frozenset({"get_ticket", "list_open_tickets"}),
    "inventory": frozenset({"check_stock", "list_vendors"}),
    "accounting": frozenset(
        {"get_cash_position", "list_open_invoices", "get_invoice", "list_payments", "project_cash_balance", "quote_bulk_order",
         "get_rent_due"}  # Problem 9: verify rent amounts itself instead of relying on a relayed figure
    ),
    "facilities": frozenset({"get_rent_due", "list_payments"}),
    "customer_service": frozenset({"get_ticket"}),
}

# Who may delegate to whom. Specialists report back to whoever called them.
DELEGATES: dict[str, tuple[str, ...]] = {
    "boss": ("inventory", "accounting", "facilities", "customer_service"),
    "customer_service": ("inventory", "accounting"),
    "facilities": ("accounting",),
    "inventory": (),
    "accounting": (),
}

AGENT_LABELS = {
    "inventory": "Inventory (stock on hand, shortfalls, other sizes, vendor lead times)",
    "accounting": "Accounting (cash, invoices, payments, pricing, discounts, cash projections)",
    "facilities": "Facilities (leases, rent due dates and amounts, the shop space)",
    "customer_service": "Customer Service (interpreting the requester's ask, drafting a reply that is never sent)",
}

MAX_CHAIN_DEPTH = 3  # boss -> specialist -> specialist
MAX_DELEGATIONS_PER_TICKET = 8
# One shared budget for the whole ticket, including every delegated run.
USAGE_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60)


class AgentNotConfigured(RuntimeError):
    pass


def build_model() -> Model:
    """gpt-6-luna through Portkey's OpenAI-compatible Responses endpoint."""
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    api_key = os.environ.get("PORTKEY_API_KEY")
    if not api_key:
        raise AgentNotConfigured("PORTKEY_API_KEY is not set (looked in the environment, Homework-5/.env, and the AI Foundations .env).")
    return OpenAIResponsesModel(
        MODEL_NAME,
        provider=OpenAIProvider(api_key=api_key, base_url=PORTKEY_BASE_URL),
        settings={"openai_reasoning_effort": "low"},
    )


@dataclass
class RunState:
    """Shared by every agent working on one ticket."""

    run_id: str
    ticket_id: int
    audit: AuditTrail
    delegations: int = 0
    cache: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    steps: dict[str, int] = field(default_factory=dict)  # per-chain step counters

    def log(self, action: str, agent: str | None, **fields: Any) -> dict[str, Any]:
        return self.audit.append(action=action, run_id=self.run_id, ticket_id=self.ticket_id, agent=agent, **fields)


@dataclass
class TeamDeps:
    state: RunState
    chain: tuple[str, ...]

    @property
    def agent(self) -> str:
        return self.chain[-1]


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return json.loads(json.dumps(value, default=str))


async def _audited_mcp_call(ctx: RunContext[TeamDeps], call_tool: CallToolFunc, name: str, args: dict[str, Any]) -> Any:
    """Every MCP call made by any agent passes through here and is logged."""
    deps = ctx.deps
    chain = list(deps.chain)
    deps.state.log("tool_call", deps.agent, chain=chain, tool={"server": "campus-customs", "name": name, "args": args})
    try:
        result = await call_tool(name, args)
    except Exception as exc:
        deps.state.log("error", deps.agent, chain=chain, tool={"name": name, "args": args}, error=f"{type(exc).__name__}: {exc}")
        raise
    deps.state.log("tool_result", deps.agent, chain=chain, tool={"name": name, "args": args, "result": _jsonable(result)})
    return result


def make_mcp_toolset() -> MCPToolset:
    """One stdio connection to the campus-customs MCP server, using this interpreter."""
    # The stdio transport only passes the variables it is given, so forward the DB override (tests use a temp copy).
    env = {k: v for k in ("PATH", "HOME", "CAMPUS_CUSTOMS_DB") if (v := os.environ.get(k))}
    client = Client(StdioTransport(command=sys.executable, args=[str(MCP_SERVER)], cwd=str(HW5_DIR), env=env))
    return MCPToolset(client, id="campus-customs", process_tool_call=_audited_mcp_call)


class Team:
    """The five agents plus their shared MCP connection and audit trail.

    `models` is one Model for every agent (live: gpt-6-luna via Portkey) or a
    dict of per-agent models (tests use scripted FunctionModels, no Portkey).
    """

    def __init__(self, models: Model | dict[str, Model] | None = None, *, audit_path: Path = AUDIT_PATH):
        if models is None:
            models = build_model()
        self.models = models if isinstance(models, dict) else {name: models for name in AGENTS}
        self.audit = AuditTrail(audit_path)
        self.mcp = make_mcp_toolset()
        self.agents: dict[str, Agent[TeamDeps, Any]] = {name: self._build_agent(name) for name in AGENTS}
        self.batch_outflows: list[dict[str, Any]] = []  # proposed (unpaid) outflows across tickets in this batch

    async def __aenter__(self) -> Team:
        await self.mcp.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.mcp.__aexit__(*exc)

    # --- construction -----------------------------------------------------

    def _build_agent(self, name: str) -> Agent[TeamDeps, Any]:
        allowed = AGENT_MCP_TOOLS[name]
        agent: Agent[TeamDeps, Any] = Agent(
            self.models[name],
            name=name,
            deps_type=TeamDeps,
            output_type=BossProposal if name == "boss" else SpecialistReport,
            instructions=(PROMPTS_DIR / f"{name}.md").read_text(),
            toolsets=[self.mcp.filtered(lambda ctx, tool_def, allowed=allowed: tool_def.name in allowed)],
            tools=[self._delegate_tool(name, target) for target in DELEGATES[name]],
            retries=2,
        )

        @agent.instructions
        def run_context(ctx: RunContext[TeamDeps]) -> str:
            return (
                f"Current ticket: #{ctx.deps.state.ticket_id}. "
                f"Delegation chain so far: {' -> '.join(ctx.deps.chain)}. "
                "Get every shop fact from your tools or from a specialist's report."
            )

        return agent

    def _delegate_tool(self, caller: str, target: str) -> Tool[TeamDeps]:
        async def delegate(ctx: RunContext[TeamDeps], task: str) -> dict[str, Any]:
            return await self._delegate(ctx, target, task)

        return Tool(
            delegate,
            name=f"delegate_to_{target}",
            description=(
                f"Ask the {AGENT_LABELS[target]} specialist to do one specific task for the current ticket. "
                "Include the exact record fields it needs. Returns its SpecialistReport (facts with sources, "
                "recommendations, proposed actions, concerns). Ask once per ticket; repeats return the earlier answer."
            ),
        )

    # --- running ----------------------------------------------------------

    async def _run_agent(self, name: str, prompt: str, deps: TeamDeps, usage: RunUsage) -> Any:
        state = deps.state
        chain = list(deps.chain)
        key = "->".join(chain)
        state.log("agent_start", name, chain=chain, details={"prompt": prompt, "mcp_tools": sorted(AGENT_MCP_TOOLS[name]),
                                                             "may_delegate_to": list(DELEGATES[name])})
        try:
            async with self.agents[name].iter(prompt, deps=deps, usage=usage, usage_limits=USAGE_LIMITS) as run:
                async for node in run:
                    if Agent.is_call_tools_node(node):
                        state.steps[key] = state.steps.get(key, 0) + 1
                        parts = node.model_response.parts
                        calls = [{"tool": p.tool_name, "args": p.args_as_dict()} for p in parts if isinstance(p, ToolCallPart)]
                        text = " ".join(p.content for p in parts if isinstance(p, TextPart)).strip()
                        state.log(
                            "model_step",
                            name,
                            chain=chain,
                            step=state.steps[key],
                            details={"requested_calls": calls, "text": text[:1000] or None},
                        )
            output = run.result.output
        except Exception as exc:
            state.log("error", name, chain=chain, error=f"{type(exc).__name__}: {exc}")
            raise
        state.log("agent_output", name, chain=chain, details=output.model_dump())
        return output

    async def _delegate(self, ctx: RunContext[TeamDeps], target: str, task: str) -> dict[str, Any]:
        deps = ctx.deps
        state = deps.state
        caller = deps.agent
        delegation = {"from": caller, "to": target, "task": task, "chain": list(deps.chain)}

        def blocked(reason: str) -> dict[str, Any]:
            state.log("delegation_blocked", caller, delegation=delegation, error=reason)
            return {"blocked": True, "reason": reason}

        if target not in DELEGATES[caller]:
            return blocked(f"{caller} may not delegate to {target}.")
        if target in deps.chain:
            return blocked(f"{target} is already in the chain {' -> '.join(deps.chain)}; no loops.")
        if len(deps.chain) >= MAX_CHAIN_DEPTH:
            return blocked(f"Delegation depth limit ({MAX_CHAIN_DEPTH}) reached; answer with what you have.")
        cache_key = (target, " ".join(task.lower().split()))
        if cache_key in state.cache:
            state.log("delegation_reused", caller, delegation=delegation)
            return {**state.cache[cache_key], "note": "Repeat request: this is the earlier answer, not a new run."}
        if state.delegations >= MAX_DELEGATIONS_PER_TICKET:
            return blocked(f"Delegation limit ({MAX_DELEGATIONS_PER_TICKET} per ticket) reached; consolidate what you have.")

        state.delegations += 1
        state.log("delegation_request", caller, delegation=delegation)
        child = TeamDeps(state=state, chain=deps.chain + (target,))
        prompt = f"Ticket #{state.ticket_id}. Task from {caller}: {task}"
        try:
            report: SpecialistReport = await self._run_agent(target, prompt, child, ctx.usage)
        except Exception as exc:
            state.log("delegation_failed", caller, delegation=delegation, error=f"{type(exc).__name__}: {exc}")
            return {"error": f"{target} could not complete the task: {type(exc).__name__}", "agent": target}

        result = report.model_dump()
        if result["ticket_id"] != state.ticket_id:
            result["concerns"] = [*result["concerns"], f"Report said ticket #{result['ticket_id']}; corrected to #{state.ticket_id}."]
            result["ticket_id"] = state.ticket_id
        state.cache[cache_key] = result
        state.log("delegation_result", caller, delegation={**delegation, "returned_by": target}, details=result)
        return result

    async def _guardrail_mcp_call(self, state: RunState, name: str, args: dict[str, Any]) -> dict[str, Any]:
        state.log("tool_call", "guardrails", tool={"server": "campus-customs", "name": name, "args": args})
        result = await self.mcp.direct_call_tool(name, args)
        state.log("tool_result", "guardrails", tool={"name": name, "args": args, "result": _jsonable(result)})
        return result

    async def resolve(self, ticket_id: int) -> TicketResolution:
        """Run the Boss on one ticket, apply the guardrails, and return the proposal."""
        state = RunState(run_id=uuid4().hex[:12], ticket_id=ticket_id, audit=self.audit)
        model_names = sorted({getattr(m, "model_name", type(m).__name__) for m in self.models.values()})
        state.log("run_start", "boss", details={"models": model_names, "database": "data/campus_customs_new.db (via MCP)",
                                                 "usage_limits": {"request_limit": USAGE_LIMITS.request_limit,
                                                                  "tool_calls_limit": USAGE_LIMITS.tool_calls_limit}})
        usage = RunUsage()
        try:
            proposal: BossProposal = await self._run_agent(
                "boss",
                f"Resolve ticket #{ticket_id}. Propose a resolution for human review; do not execute anything.",
                TeamDeps(state=state, chain=("boss",)),
                usage,
            )
            resolution, outflows = await apply_guardrails(
                proposal,
                ticket_id=ticket_id,
                call_mcp=lambda name, args: self._guardrail_mcp_call(state, name, args),
                prior_outflows=self.batch_outflows,
            )
        except Exception as exc:
            state.log("run_end", "boss", error=f"{type(exc).__name__}: {exc}", details={"status": "failed", "requests": usage.requests})
            raise
        resolution.run_id = state.run_id
        self.batch_outflows.extend(outflows)
        for check in resolution.rule_checks:
            state.log("guardrail_check", "guardrails", details=check.model_dump())
        state.log("resolution", "boss", approval_status=resolution.approval_status, details=resolution.model_dump())
        state.log("run_end", "boss", approval_status=resolution.approval_status,
                  details={"status": "proposed", "delegations": state.delegations, "requests": usage.requests,
                           "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens})
        return resolution
