# Campus Customs Operations Desk: Design

The dashboard (`frontend/`, React + Vite + TypeScript) is the human's side of the multi-agent system. The agents investigate and propose; the person at the desk watches, reviews, and decides. Every design choice serves that split: make the agents' work easy to follow, and make the human's decision deliberate and well-informed.

## Concept: a paper desk under a navy masthead

The look is an **operations desk**, not an admin template:

- **Masthead.** A Yale-navy masthead with a gold rule sits over a warm, paper-coloured workspace (`#f3efe6`). The paper suggests case files and ledgers instead of a SaaS grey. The navy and gold tie it to Campus Customs' Yale identity, the same Bulldog Blue palette as Homework 4.
- **Two typefaces with distinct jobs.**
  - **Ledger serif** (Iowan Old Style / Charter / Georgia, all system fonts with nothing downloaded) for money, ticket subjects, and proposal text, the things a person *reads and decides on*.
  - **System sans and mono** for interface chrome, tool names, SKUs, and timestamps, the things a person *scans*.

  Money always uses tabular numerals, so amounts line up.
- **Physical metaphors where they help.**
  - A proposed payment is a **payment slip** with a perforated stub, a large amount, and "Pay to / For / Ref" lines.
  - Approval stamps it with a slightly rotated green **APPROVED** stamp.
  - The customer reply is a **letter** with a red **DRAFT · NOT SENT** stamp, so nobody mistakes it for something already sent.
  - Rule checks are **PASS / FAIL stamps**.
- **Agent identity colours.** Each agent has one colour and a monogram, used everywhere it appears: crew strip, feed, handoffs, crew report, and fact sources. After a minute you read the feed by colour.

| Agent | Colour | Monogram |
|---|---|---|
| Boss | navy | B |
| Customer Service | burnt orange | CS |
| Inventory | teal | IN |
| Accounting | ochre | AC |
| Facilities | violet | FA |
| You (human) | green | ★ |

## Layout

Three columns on a wide screen, in reading order: **what's waiting → what happened → what to decide**.

```
┌ masthead: brand · desk day · backend status ·  [ CHECKING $3,400.00 | awaiting approval | if all approved ] ┐
├───────────────┬───────────────────────────────────────────────┬─────────────────────────────┤
│ TICKET QUEUE  │ CASE FILE                                       │ DECISION                    │
│ #101 card     │  ticket header + facts + [Run the agent team]   │  proposal summary           │
│ #102 card     │  run tabs (history)                             │  recommended option         │
│ #103 card     │  crew strip (5 agents, live state)              │  payment slips / empty state│
│               │  agent activity timeline (live)                 │  other actions + why        │
│               │  crew report (after the run)                    │  draft reply · rule checks  │
└───────────────┴───────────────────────────────────────────────┴─────────────────────────────┘
```

- **Placement:** the queue and the decision panel are sticky, so the checking balance, the tickets, and the approve button stay in view while you scroll a long feed.
- **Under 1360px:** the decision panel moves under the case file.
- **Under 860px:** everything stacks into one column, the queue scrolls sideways, and the ledger sits under the masthead. Tested at 375px with no horizontal overflow.

## Tickets and resolution

- **Ticket card:** each card shows a type icon (tee for customer order, building for rent notice, tag for price override), the ticket number, the subject in serif, the requester, and the item line (`1 × CC-TEE-WHITE · size S` or `Lease 1`).
- **Status:** a clear **Open** (navy) / **Resolved** (green, check icon) pill comes straight from the backend's `status`. Resolved cards get a faint green wash. A resolved ticket's case file says why it's resolved, and its run button is disabled.
- **Footer badge:** shows where the ticket stands: *Team working* (pulsing), *N awaiting approval* (amber), *Last run failed* (red), *Proposal on file*, or *Not run yet*.

## Agent activity

The feed is built from the audit trail (`GET /api/events`), so it shows exactly what the agents did, never a reconstruction:

- **Crew strip.** All five agents sit in a row. While a run is live, the active agent's avatar pulses in its colour. Afterwards each shows its tool-call count, or *Not needed* if the Boss didn't call it. This makes the delegation boundary visible at a glance: on #102 only Boss, Facilities, and Accounting light up.
- **Timeline.** One row per meaningful step, indented by delegation depth (Boss → Customer Service → Inventory nests twice):
  - **Handoffs:** `Boss → Inventory` with the exact task quoted, tinted in the receiving agent's colour.
  - **Tool calls:** the real MCP call (`check_stock(sku "CC-TEE-WHITE", size "S", qty 1)`) with its result as a few labelled chips (on hand 0 · short 1 · other sizes M 5 · L 3 · XL 2). A **raw** toggle shows the full JSON. Each call is paired with its result; until the result arrives it shows "waiting for MCP…".
  - **Reports:** what each specialist told its caller.
  - **Guardrails and markers:** guardrail PASS/FAIL stamps, the proposal-ready marker, and run start and end with the model-call count.
  - **Approvals:** human approvals and refusals appear in the same timeline.
- **Live updates.** While a run is in progress the dashboard polls about every 1.2 s, fetching only new events (`after_seq`), and shows "Waiting for the next step…". Otherwise it refreshes every 6 s. No manual reload is needed.
- **Run tabs.** Every run of a ticket is kept, including the Problem 5 live run, and the newest is followed automatically.
- **Crew report.** When a run finishes, one card per agent that took part shows who asked it, its final summary in its own words, and the MCP tools it used.

## Cash and approvals

- **The ledger in the masthead.**
  - **Checking** is the largest number on the page.
  - **Awaiting approval** shows the total of payable proposals.
  - **If all approved** shows the balance after paying all of them, and turns red if that would be negative.

  When the balance changes after an approval, the ledger flashes gold once so the change is noticed.
- **Payment slips** appear only for actions the backend marks `approvable`: a payment or purchase with a verified amount that hasn't been approved since the last reset. Each slip shows the amount, payee, purpose, reference, and *Awaiting your approval*.
- **Approval is a deliberate act.**
  1. *Review & approve* opens a dialog with the amount, payee, purpose, ticket, and a **cash preview** (checking now → after).
  2. You must type your **name** and tick **"I approve paying $X to Y"** before the button enables.
  3. If the payment would take checking below $0, the dialog says so and keeps the button disabled.
  4. The request goes to `POST /api/approvals` with `confirm: true` and the exact amount. The backend re-checks everything.
  5. A refusal (e.g. 409 insufficient cash) appears inside the dialog, which stays open.
  6. Success stamps the slip **Approved by <name> · payment #N**, updates the ledger, and shows the ticket as Resolved once the backend reports it.
- **Other proposed actions** (customer reply, substitute offer, discount offer, blocked items) are listed separately, each with the reason it isn't a payment ("Draft for a human to send", "Blocked: no amount to check against cash", …).
- **Empty state.** When the saved proposal has nothing payable, which is true of all three Problem 5 proposals, the panel says so and explains why. It also notes that a new run might produce one, but that a run uses Portkey credits and only starts when you press the button. It never invents a proposal or starts a run on its own.

## Safety in the interface

- **Nothing happens on view.** Selecting or viewing a ticket never sends a request that changes anything; a test asserts zero POSTs.
- **Runs need two clicks.** *Run the agent team* opens a confirmation that states the cost (gpt-6-luna via Portkey, typically 12–20 model calls) and that agents only propose.
- **Approvals** need a name, an explicit checkbox, and the backend's own validation.
- **Reset** sits in a tools menu and requires typing **RESET**.
- **No direct data access.** The frontend only calls the Problem 7 routes; it has no database access.

## States

- **Loading:** shimmering skeleton cards and panels, and "Connecting…" in the masthead.
- **Backend offline:** a red banner with the exact command to start it (`uvicorn main:app --reload --port 8000`). The page keeps retrying, and the masthead shows *Backend offline*.
- **Errors:** failed requests produce toasts with the backend's own message. Errors stay until dismissed; successes fade.
- **Empty:** no runs yet ("Run the agent team to watch Boss route the ticket…"), no proposal, nothing to approve.

## Why this works

- **Context in one place.** Without switching pages, a person can see what's waiting, how the team handled it, and what money is at stake.
- **Traceable.** The feed shows *who* did *what* with *which data*, in colour, with real tool results, so the proposal can be checked against its evidence.
- **Clear boundary between proposal and action.** Proposals look like paperwork; only explicit, confirmed human approval moves money.
- **Calm by default, attention-grabbing only when it matters:** pulsing for live work, amber for waiting on you, red for refusals and failures, green for done.
- **Accessible:**
  - semantic landmarks (navigation, main, complementary);
  - real buttons;
  - modal dialogs that trap focus and close on Esc;
  - `aria-live` on the feed and balance;
  - visible focus rings;
  - reduced-motion support;
  - colour never used alone (pills and stamps also carry text).

## Resolution step (added in Problem 9)

A ticket can now be closed by a human even when its proposal has nothing to pay:

- **Resolution card.** Below the payment slips sits a **Resolution** card with *Approve resolution…*. If payments are still awaiting a decision, the card says so.
- **Resolve dialog.** It shows the team's recommended option, what has been paid, and "Resolving moves no money and sends nothing". It requires your **name** and an explicit **"I approve resolving ticket #N as proposed"**. Any pending payment must be explicitly ticked as **left unpaid** before the button enables.
- **Backend.** The request goes to `POST /api/tickets/{id}/resolve` with the latest `run_id`, so an outdated proposal can't be resolved.
- **Payment dialog default.** "Mark ticket resolved" is pre-ticked only when this is the ticket's **last** pending payment, so approving one payment never silently closes a ticket that still has another.
- **Your decisions.** Approvals and resolutions appear in a **Your decisions** list under the agent timeline.
- **Header chip.** For a resolved ticket, the decision header reads **resolved by a human**, not the proposal's status at run time.
