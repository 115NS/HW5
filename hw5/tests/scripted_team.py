"""Scripted stand-ins for gpt-6-luna, for offline tests (no Portkey calls).

Each agent gets a PydanticAI FunctionModel driven by a small "planner" that
decides the next tool call from what the tools have returned so far. Planners
never contain shop values: every number in their output is copied from an MCP
result or a specialist report, so the tests can check them against the DB.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Callable

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

Returns = dict[str, list[Any]]  # tool name -> results in call order
Plan = tuple[str, dict[str, Any]]  # ("tool_name", args) or ("final", output)


def _content(part: ToolReturnPart) -> Any:
    c = part.content
    if isinstance(c, str):
        try:
            return json.loads(c)
        except ValueError:
            return c
    if hasattr(c, "model_dump"):
        return c.model_dump()
    return c


def _prompt(messages: list[ModelMessage]) -> str:
    for m in messages:
        if isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, UserPromptPart) and isinstance(p.content, str):
                    return p.content
    return ""


def _returns(messages: list[ModelMessage]) -> Returns:
    out: Returns = {}
    for m in messages:
        if isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, ToolReturnPart):
                    out.setdefault(p.tool_name, []).append(_content(p))
    return out


def scripted(planner: Callable[[str, Returns], Plan], name: str) -> FunctionModel:
    def fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool, args = planner(_prompt(messages), _returns(messages))
        if tool == "final":
            tool = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool, args)])

    return FunctionModel(fn, model_name=f"scripted-{name}")


def _tid(prompt: str) -> int:
    return int(re.search(r"#(\d+)", prompt).group(1))


def _kv(prompt: str, key: str) -> str | None:
    m = re.search(rf"\b{key}=([\w.-]+)", prompt)
    return m.group(1) if m else None


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _report(agent: str, tid: int, summary: str, facts, recs, actions=(), concerns=()) -> Plan:
    return ("final", {"agent": agent, "ticket_id": tid, "summary": summary, "facts": list(facts),
                      "recommendations": list(recs), "proposed_actions": list(actions), "concerns": list(concerns)})


# --- specialists ---------------------------------------------------------


def inventory(prompt: str, r: Returns) -> Plan:
    tid = _tid(prompt)
    sku, size, qty = _kv(prompt, "sku"), _kv(prompt, "size"), int(_kv(prompt, "qty"))
    if "check_stock" not in r:
        return ("check_stock", {"sku": sku, "size": size, "qty": qty})
    if "list_vendors" not in r:
        return ("list_vendors", {"specialty": "apparel"})
    s, v = r["check_stock"][0], r["list_vendors"][0]["vendors"][0]
    facts = [
        {"label": f"{sku} {s['size']} on hand", "value": str(s["on_hand"]), "source": "check_stock"},
        {"label": "shortfall", "value": str(s["shortfall"]), "source": "check_stock"},
        {"label": "other sizes", "value": ", ".join(f"{o['size']} {o['qty']}" for o in s["other_sizes"]), "source": "check_stock"},
        {"label": "apparel vendor", "value": f"{v['name']}, {v['lead_days']} lead days", "source": "list_vendors"},
    ]
    actions = []
    if s["shortfall"]:
        actions.append({"kind": "restock_order", "description": f"Reprint {s['shortfall']} x {sku} {s['size']} from {v['name']}",
                        "payee": v["name"], "ref": f"{sku} {s['size']}"})
    return _report("inventory", tid, f"{s['on_hand']} on hand; shortfall {s['shortfall']}.", facts,
                   [f"{v['name']} lead time {v['lead_days']} days."], actions)


def accounting(prompt: str, r: Returns) -> Plan:
    tid = _tid(prompt)
    invoice_id, rent, sku, qty = _kv(prompt, "invoice"), _kv(prompt, "rent"), _kv(prompt, "sku"), _kv(prompt, "qty")
    if "get_cash_position" not in r:
        return ("get_cash_position", {})
    if invoice_id and "get_invoice" not in r:
        return ("get_invoice", {"invoice_id": int(invoice_id)})
    if rent and "list_open_invoices" not in r:
        return ("list_open_invoices", {})
    if rent and "project_cash_balance" not in r:
        outflows = [{"label": "Rent", "amount": float(rent)}] + [
            {"label": f"Invoice {i['invoice_id']}", "amount": i["amount"]} for i in r["list_open_invoices"][0]["invoices"]]
        return ("project_cash_balance", {"outflows": outflows})
    if sku and len(r.get("quote_bulk_order", [])) < 3:
        return ("quote_bulk_order", {"sku": sku, "qty": int(qty), "discount_pct": [0, 10, 15][len(r.get("quote_bulk_order", []))]})

    cash = r["get_cash_position"][0]["total_balance"]
    facts = [{"label": "cash on hand", "value": _money(cash), "source": "get_cash_position"}]
    recs, actions, concerns = [], [], []
    if "get_invoice" in r:
        inv = r["get_invoice"][0]["invoice"]
        facts.append({"label": f"invoice {inv['invoice_id']}", "value": f"{_money(inv['amount'])} {inv['status']}, due {inv['due_date']} ({inv['days_until_due']} days)", "source": "get_invoice"})
        if inv["overdue"]:
            concerns.append(f"Invoice {inv['invoice_id']} is overdue; the reprint may be held until it is paid.")
    if "project_cash_balance" in r:
        p = r["project_cash_balance"][0]
        facts.append({"label": "cash after rent + open invoices", "value": _money(p["ending_balance"]), "source": "project_cash_balance"})
        recs.append("Rent can be paid without cash going negative." if p["stays_non_negative"] else "Cash would go negative; prioritise.")
    for q in r.get("quote_bulk_order", []):
        facts.append({"label": f"{q['discount_pct']:g}% off x{q['qty']}", "value": f"{_money(q['total_revenue'])} revenue, {_money(q['gross_profit'])} profit, {q['margin_pct']}% margin", "source": "quote_bulk_order"})
    if "quote_bulk_order" in r:
        recs.append("Any discount up to 15% stays above unit cost.")
    return _report("accounting", tid, "Financial review complete.", facts, recs, actions, concerns)


def facilities(prompt: str, r: Returns) -> Plan:
    tid = _tid(prompt)
    lease = int(_kv(prompt, "lease"))
    if "get_rent_due" not in r:
        return ("get_rent_due", {"lease_id": lease})
    if "list_payments" not in r:
        return ("list_payments", {"kind": "rent", "ref_id": lease})
    rd = r["get_rent_due"][0]
    if "delegate_to_accounting" not in r:
        return ("delegate_to_accounting", {"task": f"rent={rd['monthly_rent']:g} due {rd['next_due']} for lease {lease}: confirm cash stays non-negative with open invoices."})
    acct = r["delegate_to_accounting"][0]
    facts = [
        {"label": "rent due", "value": f"{_money(rd['monthly_rent'])} on {rd['next_due']} ({rd['days_until_due']} days)", "source": "get_rent_due"},
        {"label": "rent payments already made", "value": str(r["list_payments"][0]["count"]), "source": "list_payments"},
        *[{**f, "source": "accounting"} for f in acct.get("facts", [])],
    ]
    action = {"kind": "payment", "description": f"Pay {rd['space_name']} rent to {rd['landlord']}", "amount": rd["monthly_rent"],
              "payee": rd["landlord"], "ref": f"lease {lease}"}
    return _report("facilities", tid, "Rent matches the lease record.", facts, acct.get("recommendations", []), [action])


def customer_service(prompt: str, r: Returns) -> Plan:
    tid = _tid(prompt)
    if "get_ticket" not in r:
        return ("get_ticket", {"ticket_id": tid})
    t = r["get_ticket"][0]["ticket"]
    if "delegate_to_inventory" not in r:
        return ("delegate_to_inventory", {"task": f"sku={t['sku']} size={t['size']} qty={t['qty']}: can we fill it, and what are the options?"})
    if t["type"] == "price_override" and "delegate_to_accounting" not in r:
        return ("delegate_to_accounting", {"task": f"sku={t['sku']} qty={t['qty']}: quote list price and 10% / 15% discounts."})
    inv = r["delegate_to_inventory"][0]
    if "error" in inv:  # a failed delegation comes back as {"error": ...}; report it, don't guess stock
        return _report("customer_service", tid, "Stock could not be checked.", [], [], [], [inv["error"]])
    facts = [{**f, "source": "inventory"} for f in inv["facts"]]
    if "delegate_to_accounting" in r:
        facts += [{**f, "source": "accounting"} for f in r["delegate_to_accounting"][0]["facts"]]
    draft = f"Draft reply: Hi {t['requester']}, thanks for your order. {inv['summary']} We'll confirm options shortly."
    action = {"kind": "customer_reply", "description": f"Send reviewed reply to {t['requester']}", "payee": t["requester"]}
    return _report("customer_service", tid, f"{t['requester']} wants {t['qty']} x {t['sku']} {t['size']}.", facts, [draft], [action])


# --- boss -----------------------------------------------------------------


def boss(prompt: str, r: Returns) -> Plan:
    tid = _tid(prompt)
    if "get_ticket" not in r:
        return ("get_ticket", {"ticket_id": tid})
    t = r["get_ticket"][0]["ticket"]
    plan: list[tuple[str, str]] = []
    if t["type"] in ("customer_order", "price_override"):
        plan.append(("delegate_to_customer_service", f"Interpret the request from {t['requester']} and draft a reply."))
    if t["type"] == "customer_order" and t["invoice_id"]:
        plan.append(("delegate_to_accounting", f"invoice={t['invoice_id']}: status of the reprint invoice linked to this order."))
    if t["type"] == "rent_notice":
        plan.append(("delegate_to_facilities", f"lease={t['lease_id']}: confirm rent owed and whether it can be paid."))
    for tool, task in plan:
        if tool not in r:
            return (tool, {"task": task})

    reports = [r[tool][0] for tool, _ in plan]
    facts, actions, concerns, draft = [], [], [], None
    for rep in reports:
        facts += [{**f, "source": f"{rep['agent']} via {f['source']}"} for f in rep["facts"]]
        actions += rep["proposed_actions"]
        concerns += rep["concerns"]
        for rec in rep["recommendations"]:
            if rec.startswith("Draft reply:"):
                draft = {"to": t["requester"], "subject": f"Re: {t['subject']}", "body": rec.removeprefix("Draft reply:").strip()}
    return ("final", {
        "ticket_id": tid, "ticket_type": t["type"], "summary": f"Ticket #{tid} ({t['type']}) reviewed by {len(reports)} specialist(s).",
        "delegated_to": [rep["agent"] for rep in reports], "key_facts": facts,
        "options": ["Proceed as proposed after human approval", "Wait"], "recommended_option": "Proceed as proposed after human approval",
        "proposed_actions": actions, "customer_reply_draft": draft, "open_questions": concerns,
    })


PLANNERS = {"boss": boss, "inventory": inventory, "accounting": accounting, "facilities": facilities,
            "customer_service": customer_service}


def scripted_models(**overrides: Callable[[str, Returns], Plan]) -> dict[str, FunctionModel]:
    return {name: scripted(overrides.get(name, planner), name) for name, planner in PLANNERS.items()}


def eta(desk_date: str, lead_days: int) -> str:
    return (date.fromisoformat(desk_date) + timedelta(days=lead_days)).isoformat()
