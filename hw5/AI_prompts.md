# Homework 5: Campus Customs Multi-Agent Operations System — AI Prompts

## Problem 1: Set up AI_prompts.md

### Prompt

> I’m starting Homework 5 for AI Foundations. We’re building a Campus Customs multi-agent operations system with an MCP server, a FastAPI backend, and a React dashboard. The system will have five agents: Boss, Inventory, Accounting, Facilities, and Customer Service. They need to work together and delegate tasks to each other to resolve shop tickets.
> We’ll work through the homework one problem at a time. Please inspect the existing project and data first, but don’t start solving any problems until I give you the specific task for Problem 1. Use only gpt-6-luna through Portkey for every AI call, as required by the assignment. Keep the original database untouched and use a separate working copy named data/campus_customs_new.db. Follow the shop rules, especially that payments require human approval, cash cannot go negative, and no real customers or vendors should be contacted. Keep AI_prompts.md updated with the prompts I actually send you, recording one section per problem and including follow-ups only when I actually send them. Don’t invent prompts or follow-ups.
> Problem 1 prompt
> Please set up AI_prompts.md for Homework 5. I need one section for each problem, with the problem number and title, at least one prompt I actually send you written as close to verbatim as possible, and a follow-up prompt only if I send one, along with one sentence explaining what was missing after the first prompt. Don’t fill in prompts for future problems or invent follow-ups. Keep the file updated as we work through the homework, one problem at a time.

### Follow-up prompt

What was missing: the first prompt didn't say where the Homework 5 data pack was, and I wrongly reported the data as missing instead of finding `data/campus_customs.db` myself.

> I’ve confirmed that the Homework 5 data is already in the project folder. Please check the existing files and locate the data pack yourself before concluding that anything is missing. Verify that data/campus_customs.db is present, and make sure the original database remains untouched. If the required files are there, continue with the assignment as planned. Don’t download or create duplicate data files.
> Keep working one problem at a time, use gpt-6-luna through Portkey as required by the assignment, and continue updating AI_prompts.md with the actual prompts and any follow-ups I send.

## Problem 2: Study the Campus Customs database

### Prompt

> I want to complete Problem 2: Study the Campus Customs database.
>
> Please inspect the existing project and data files first. Open data/campus_customs.db and examine every table and its fields. Copy the original database to data/campus_customs_new.db, which we will use for later problems. Do not modify the original database.
>
> Study the three open tickets and trace how they connect to the other tables. I want to understand the database structure and how the different tables relate to the tickets.
>
> Start or update output/harness.md. For every table in the database, list its fields and include one short sentence explaining why that table matters for the agents we will build.
>
> Please make sure the database copy works, document the actual schema rather than guessing, and keep the harness organized so we can continue adding to it in later problems.
>
> Update AI_prompts.md with the actual prompt I used for Problem 2. Do not invent any follow-up prompts; only record a follow-up if I actually send one. Do not start Problem 3.

## Problem 3: Build the MCP server

### Prompt

> I want to build the MCP server for Problem 3. Please create the mcp_server/ folder and implement three useful tools using FastMCP that work with data/campus_customs_new.db.
> Choose three tools that help resolve the three open tickets (#101, #102, and #103). Use the actual database records and don't invent any data. Make sure each tool has a clear name and returns the information needed to resolve its ticket.
> In output/harness.md, list all three tools, the table each one reads, which ticket it helps resolve, and one sentence explaining why the tool is appropriate for that ticket. Be specific about how each tool connects to its ticket rather than just saying it reads a table.
> Also create mcp_server/README.md explaining what the MCP server does, which database file it uses, and the three tools it provides. You don't need to connect or run the MCP server yet.
> Please update AI_prompts.md with the actual prompt I used for Problem 3. Only add a follow-up if I actually send one, with one sentence explaining what was missing from the first prompt.

## Problem 4: Connect the MCP server to Claude Code and test the tools

### Prompt

> I want to connect the MCP server to Claude Code and test all three tools for Problem 4.
> Please inspect the existing mcp_server/ implementation and configure it for this project using FastMCP. Save the connection configuration in .mcp.json at the project root, using the correct local paths and the Python environment already created for Homework 5. Don’t expose any API keys or other secrets in the configuration.
> Once it is configured, help me make the server available to Claude Code. If I need to restart Claude Code or approve the server, tell me exactly what to do rather than assuming it is connected.
> After the connection is active, test each of the three MCP tools through Claude Code itself, not by calling the Python functions directly. Save the evidence in output/mcp_smoke.json. For each tool, include the prompt I used, the exact tool name, and the actual output returned. Verify that the returned values match data/campus_customs_new.db, and don’t invent or change any database values to make the tests pass.
> Update output/harness.md with the connection setup and testing details, and update AI_prompts.md with the actual prompt used for Problem 4. Add a follow-up only if I actually send one, with one sentence explaining what was missing from the first prompt.
> Don’t move on to Problem 5.

### Follow-up prompt

What was missing: the first prompt couldn't be finished in one go, because Claude Code only loads a new MCP server when a session starts, so the tests had to wait until the connection was active.

> Continue Problem 4. Check whether the campus-customs MCP server is connected and available. If it is, test all three tools through Claude Code, verify their outputs against data/campus_customs_new.db, save the actual results and prompts in output/mcp_smoke.json, and finish updating output/harness.md and AI_prompts.md. If the server is not available, help me fix the connection first. Do not invent test results or move on to Problem 5.

### Follow-up prompt 2

What was missing: the server still wasn't loaded, because the previous follow-up was sent in the same Claude Code session that existed before `.mcp.json` was updated.

> Continue Problem 4. Test check_stock, get_rent_due, and quote_bulk_order through the connected campus-customs MCP server. Verify the actual outputs against data/campus_customs_new.db and save each prompt, exact tool name, and actual output to output/mcp_smoke.json. Finish the Problem 4 section in output/harness.md and make sure AI_prompts.md contains the actual prompts and only the follow-ups I sent. Do not invent results, change the original database, or start Problem 5.

### Follow-up prompt 3

Why it was needed: after several "continue" attempts the server still wasn't available, and I had only suggested restarting instead of finding out whether the server, the config, or Claude Code's loading process was at fault.

> I think something may be wrong with how we configured the MCP server in Problem 4. We've tried connecting several times, but campus-customs still isn't available.
>
> Please investigate the setup instead of asking me to restart Claude Code again.
>
> Check the MCP server implementation from Problem 3, both .mcp.json files, the configured working directory, Python executable paths, and whether Claude Code is actually discovering the server configuration. Check for any configuration or startup errors.
>
> I want you to identify whether the problem is with the server itself, the MCP configuration, or Claude Code's connection and approval process. Don't assume that restarting the session is the only solution.
>
> If you find a configuration issue, fix it and explain exactly what was wrong. If the configuration is correct but Claude Code isn't loading it, tell me the specific action I need to take in the interface and how to verify the connection.
>
> Please don't create fake test results or mark Problem 4 complete. Once the connection works, we can test the three tools and finish output/mcp_smoke.json.
>
> Update AI_prompts.md with this actual follow-up and a sentence explaining why it was needed. Don't move on to Problem 5.

### Follow-up prompt 4

Why it was needed: the earlier attempts didn't get `campus-customs` connected, so the connection had to be re-checked before the three tools could be tested.

> Continue Problem 4. First confirm that campus-customs is connected and its three tools are available. Then test check_stock, get_rent_due, and quote_bulk_order through Claude Code itself. Verify the actual outputs against data/campus_customs_new.db and save the prompts, exact tool names, and actual outputs to output/mcp_smoke.json. Finish the Problem 4 section in output/harness.md and ensure AI_prompts.md contains the actual prompts and only the follow-ups I sent. Do not invent results, modify the original database, or start Problem 5.

### Follow-up prompt 5

Why it was needed: my earlier replies kept saying "start a new session" without proving where the failure was or trying a fix from the terminal, so the user asked me to take ownership of the root cause and fix it.

> Please take ownership of troubleshooting the Problem 4 MCP connection. I want you to fix the setup, not just tell me repeatedly to start a new session.
>
> The `campus-customs` MCP server is configured in `.mcp.json`, and its Python server reportedly starts and completes the MCP handshake when launched manually. However, Claude Code does not discover the server or expose its three tools.
>
> Please investigate the root cause and identify a practical fix. Check the project-level and parent-level MCP configurations, the working directory, the exact Python interpreter and server paths, Claude Code's MCP configuration-loading behavior, and whether there is a supported way to reload or add the server to this session. If a terminal command or configuration change can fix this, make the change yourself where possible. Ask me to perform a UI action only when you genuinely need my input.
>
> Do not claim the connection works unless you verify that Claude Code can actually see and invoke the three MCP tools. Once connected, test `check_stock`, `get_rent_due`, and `quote_bulk_order` through Claude Code itself, verify their outputs against `data/campus_customs_new.db`, and save the actual results in `output/mcp_smoke.json`. Update `output/harness.md` and `AI_prompts.md` with the real work performed. Do not invent test results, modify the original database, expose secrets, or start Problem 5. If the current session cannot load the server, explain the specific technical limitation and give me the simplest workaround.

_Note: the smoke tests (`output/mcp_smoke.json`, 3/3 pass) ran in a separate, newly started Code-tab session (`Finish HW5 Problem 4 MCP smoke tests`) launched from a Claude-drafted task chip; that chip prompt was written by Claude, not typed by the user, so it is not logged as a prompt._

### Follow-up prompt 6

Why it was needed: the harness recorded the diagnosis and final results but not a clear step-by-step account of the troubleshooting, so the user asked for one that keeps failed attempts separate from the successful tests.

> Please document the troubleshooting process for Problem 4 so my professors can see how I diagnosed and resolved the MCP connection issue. Update the existing `output/harness.md` and `AI_prompts.md` without changing the successful smoke-test results or starting Problem 5.
> In `output/harness.md`, add a short chronological troubleshooting section covering:
>
> 1. The initial issue: `campus-customs` was missing from the existing Claude Code session's connector list, and none of its three tools were available.
> 2. The diagnosis: the existing session had started before the MCP configuration was added, so it did not load the new server.
> 3. The checks performed: validation of both `.mcp.json` files, verification of the absolute paths and Python environment, a manual server startup and MCP handshake, and inspection of Claude Code's MCP configuration.
> 4. The intermediate attempt: a separate terminal-launched Claude Code process connected to the server and exposed all three tools, but could not call them because it was not logged in. State this limitation accurately; do not imply that the terminal process performed the smoke tests.
> 5. The resolution: a separate, newly started Code-tab session named `Finish HW5 Problem 4 MCP smoke tests` connected successfully and called all three tools. Their outputs were verified against `data/campus_customs_new.db` using read-only SQL checks.
> 6. The final status: all three tests passed, `output/mcp_smoke.json` was created, and Problem 4 is complete.
>
> Keep this concise and factual. Distinguish failed attempts and diagnostic checks from the final successful tests. Do not include credentials, secrets, or unsupported claims.
> In `AI_prompts.md`, preserve my original Problem 4 prompt and the follow-ups I actually sent. Do not represent assistant-generated task-chip instructions as prompts I personally wrote. If needed, add a brief note that the final tests were completed in a separate Code-tab session.
> Finally, inspect the resulting changes and report which files you updated. Do not modify either database, delete troubleshooting history, fabricate any results, or start Problem 5.

## Problem 5: Build the Campus Customs multi-agent system

### Prompt

> I want to complete Problem 5: Build the Campus Customs multi-agent system.
> Please inspect the existing project and the work completed in Problems 1–4 first. I want to build a team of five agents: Boss, Inventory, Accounting, Facilities, and Customer Service, using PydanticAI. Create a separate prompt file for each agent in `backend/prompts/`, define the required data types in `backend/models.py`, and implement the agents under `backend/`. Each agent should have a clear role, responsibilities, shop rules, and instructions on when and how to delegate work to other agents.
> The agents should work together to address the three existing open tickets:
>
> * Ticket #101: A customer wants a white tee in size S, but that size is out of stock. The team should check stock and determine what options are available without contacting the customer.
> * Ticket #102: The Chapel Street shop has rent of $2,400 due on September 2, 2026. The team should review the lease and cash position and determine what action is appropriate without making a payment.
> * Ticket #103: A customer wants 20 navy hoodies in size M, but only 8 are in stock. The team should calculate the shortfall, review the bulk-order pricing and costs, and determine the available options without contacting the customer or placing an order.
>
> Use the actual ticket records and database values rather than assuming these details are still current. The agents should obtain shop facts through MCP using `data/campus_customs_new.db`.
> Define clear delegation boundaries. The Boss agent should coordinate ticket resolution, delegate work to the appropriate specialist, and consolidate findings into a proposed resolution. The Inventory agent should handle stock checks and quantity shortfalls. The Accounting agent should review invoices, rent, cash balances, and financial calculations. The Facilities agent should handle relevant facility, lease, or maintenance issues. The Customer Service agent should interpret the customer tickets and prepare proposed responses or resolutions, but must not send messages to real customers. Agents should delegate only when another agent's expertise is needed, use the returned findings rather than inventing facts, and avoid unnecessary loops or repeated calls. The specialist agents should report their findings and recommendations to the Boss; they should not independently approve payments or override business rules.
> All agents must use `gpt-6-luna` through Portkey, using `PORTKEY_API_KEY` for authentication. Extend the existing MCP server with any additional tools the agents genuinely need, while preserving the existing tools and their behavior. Do not create a separate shop-tools layer that bypasses MCP.
> I also want an append-only audit trail in `output/audit_trail.json` that records each agent-loop step, including the ticket, agent, action, tool calls and results, delegation, errors, and approval status where relevant. The audit trail should allow us to follow how each ticket was assessed and how the agents arrived at their proposed resolutions.
> Please preserve the existing business rules: payments require human approval, cash must never go negative, and no real customers or vendors should be contacted. Do not make real payments, place real orders, or modify the original `data/campus_customs.db`. Any payment or other consequential action must be presented as a proposal for human review, not executed automatically. Do not expose secrets.
> Update `output/harness.md` cumulatively to document the agents, their responsibilities and delegation boundaries, the MCP tools and their database table mappings, the open tickets, and the safety guardrails. Update `mcp_server/README.md` to reflect the actual tools. Update `AI_prompts.md` with the actual prompt I used for Problem 5, preserving the earlier problems and recording follow-ups only if I actually send them.
> Keep the implementation focused on Problem 5 and minimize Portkey spending by using local tests or mocks wherever possible. Run appropriate tests and inspect the changes. Tell me what worked, what remains incomplete, whether any Portkey calls were made, and whether any configuration is needed from me. Do not start Problem 6.

### Follow-up prompt

Why it was needed: the first Problem 5 prompt asked to keep Portkey spending low with local tests and mocks, so the agents had only run with scripted models; this follow-up asked for a final safety review and authorized one live gpt-6-luna run of all three tickets.

> I want to finish Problem 5 by running the agents live. Before doing so, please do one final review of the implementation and safety guardrails.
>
> Check that the audit trail is currently empty, the agents are configured to use `gpt-6-luna` through Portkey, and no code path can execute payments, place orders, or send messages to real customers or vendors. Confirm that the live run will only generate proposed resolutions and append audit records, without modifying either database. Do not clear, reset, or overwrite the audit trail.
>
> If these checks pass, run all three open tickets once using the real model and the existing MCP server. Save the proposed resolutions to `output/proposed_resolutions.json` and append the actual execution records to `output/audit_trail.json`. Do not rerun tickets unnecessarily, because I want to minimize Portkey spending and avoid duplicate audit entries.
>
> After the run, inspect the proposals and audit trail. Verify that all three tickets were processed, the tool results match the database, payments remain pending human approval, cash cannot go negative, and no real-world actions were executed. Report the actual number of Portkey model calls if it can be determined, whether any errors occurred, and whether all three tickets completed successfully.
>
> If any safety check fails, stop before making model calls and explain what needs fixing. Update `output/harness.md` with the live-run results and any limitations, preserving the existing Problem 4 and Problem 5 documentation. Do not modify the original database, fabricate results, or start Problem 6. Do not add a follow-up prompt to `AI_prompts.md` unless I actually send another prompt.

## Problem 6: Plan the three tickets

### Prompt

> I want to complete Problem 6: Plan the three tickets.
>
> Please inspect the existing project, the agent implementation from Problem 5, `output/harness.md`, `output/proposed_resolutions.json`, and `output/audit_trail.json` first. I want to document what I expect the agents to do for each of the three open tickets before wiring or running the backend.
>
> Create `output/desk_tickets.html` as a page with one tab for each ticket: #101, #102, and #103. Each ticket tab should have an Expected section describing the resolution plan and leave a separate Actual section for me to fill in after the agents run. Also add empty Cash and Reflection tabs for later problems, leaving them blank or marking them “Coming later.”
>
> For each ticket’s Expected section, explain in my own words which agent the Boss should call first and why, the full delegation sequence I expect rather than having the Boss call every specialist, and which MCP tools the agents should use. Make the plans specific to the actual ticket records and database, and consistent with the agents and delegation boundaries implemented in Problem 5.
>
> For ticket #101, plan how the team should handle the unavailable white tee in size S, check stock and alternatives, and consider the reprint and invoice information where relevant. For ticket #102, plan how the team should verify the Chapel Street rent, review the cash position and outstanding invoice, and determine what should be proposed for human approval. For ticket #103, plan how the team should assess the request for 20 navy hoodies in size M, check the available stock and shortfall, review pricing and possible discounts, and determine what options should be presented without placing an order.
>
> Use actual database and MCP information rather than inventing facts. The plans should include sensible delegation boundaries and avoid sending every specialist to every ticket. Keep the Expected and Actual sections clearly separate so we can compare the plan with what really happens in a later problem.
>
> Update `output/harness.md` cumulatively if needed to document the planning deliverable. Update `AI_prompts.md` with the actual prompt I used for Problem 6, preserving all earlier entries and adding follow-ups only if I actually send them. Do not change the existing proposals or audit trail, rerun the agents, make Portkey calls, modify either database, or start Problem 7. Report the files created or updated when finished.

## Problem 7: Backend routes

### Prompt

> I want to complete Problem 7: Backend routes.
> Please inspect the existing project and the work completed in Problems 1–6 first. Build on the existing PydanticAI agents, MCP server, ticket plans, audit trail, and database setup rather than rebuilding them.
> In `backend/main.py`, use FastAPI to add the backend routes needed by the React dashboard in the next problem. The routes should:
>
> * Return the three tickets and indicate whether each is open or resolved.
> * Accept a ticket ID and run the existing agent team on that ticket.
> * Return recent agent events, including what each agent said and which tools they used, so the dashboard can refresh.
> * Allow a human to approve a proposed payment or purchase. Agents should only prepare proposals; this route should perform the approved action and update the cash balance in the working database.
> * Return the current checking balance from `cash_accounts`.
> * Reset the working database to its original values so I can test a fresh run when needed.
>
> Please follow the existing safety rules and keep all operations on `data/campus_customs_new.db`; never modify `data/campus_customs.db`. Payment or purchase approval must require an explicit human action, validate the proposal and available cash, and prevent the checking balance from going negative. Do not let agents execute payments or purchases directly. Validate ticket IDs and request bodies, handle errors clearly, and ensure the routes use the existing MCP and agent implementation wherever appropriate rather than duplicating business logic.
> From the `backend/` folder, the server should run with `uvicorn main:app --reload --port 8000` and be available at `http://localhost:8000`.
> Update `output/harness.md` cumulatively, listing each route on one line with its URL and what it does. Update `AI_prompts.md`with the actual prompt I used for Problem 7, preserving all earlier entries and recording follow-ups only if I actually send them.
> Run appropriate local tests for the routes, including validation, ticket retrieval, agent execution, approval safeguards, checking balance, and database reset. Use mocks where possible to avoid unnecessary Portkey calls. Do not perform real-world transactions, expose secrets, alter the original database, or start Problem 8. Report which routes and tests work, what remains incomplete, and whether any Portkey calls were made.

### Follow-up prompt

Why it was needed: the first Problem 7 prompt didn't ask for a review against the full route list. This follow-up asked to confirm each safeguard with tests, check that only the working database can be written, find out what was holding port 8000 without stopping it, and make sure the approver-authentication limitation was documented honestly.

> I want to finish Problem 7. Please review the implementation and verify that all the required backend routes work as described in the assignment. Check the ticket list and status, running the agent team on a ticket, retrieving recent agent events, approving a proposed payment or purchase after explicit human confirmation, retrieving the checking balance, and resetting the working database to its original values.
>
> Please inspect the existing tests and run the relevant test suite. Confirm that approval safeguards prevent unapproved actions, duplicate approvals, invalid proposals, and payments that would make cash negative. Verify that all database writes are restricted to `data/campus_customs_new.db` and that `data/campus_customs.db` remains unchanged. Do not run agents live or make Portkey calls just to test the routes.
>
> The assignment's startup command uses port 8000, but Homework 4 is already using that port. Please check whether the Homework 4 server is still running before taking any action. Do not terminate it without asking me. If port 8000 remains occupied, keep the existing server untouched and explain the simplest way to run Homework 5 on the required port when I am ready.
>
> Please also check `output/harness.md` and `AI_prompts.md`. Ensure the route list is accurate, the known limitation around approver authentication is documented honestly, and my original Problem 7 prompt is recorded without changing earlier entries. Update the harness cumulatively if needed.
>
> Do not modify either database, reset real data, change the existing audit trail or proposals, or start Problem 8. Report the test results, any remaining issues, whether any Portkey calls were made, and the files changed.

### Follow-up prompt 2

Why it was needed: before moving on, the user wanted one last check that Problem 7 was complete, including starting the backend with the exact assignment command on port 8000 now that Homework 4 no longer held it, without stopping any other server.

> Before I move on to Problem 8, please do a final check that Problem 7 is complete against both panels of the assignment. Verify that all required FastAPI routes are implemented and documented in `output/harness.md`, the tests pass, the original database remains unchanged, and `AI_prompts.md` contains my original Problem 7 prompt and only the follow-ups I actually sent.
>
> Please confirm that the backend can be started with the assignment command from the `backend/` directory: `uvicorn main:app --reload --port 8000`. Do not stop or interfere with another running server without asking me. If port 8000 is free, you may verify the Homework 5 backend on that port using read-only requests; otherwise, report the conflict without terminating another process.
>
> Do not make Portkey calls, run the agents live, change the audit trail or proposals, modify either database, or start Problem 8. Only make documentation changes if you find a genuine omission. Report the final status and any remaining limitations.

## Problem 8: Agent dashboard

### Prompt

> I want to complete Problem 8: Agent dashboard.
> Please inspect the existing project and the work completed in Problems 1–7 first, especially `backend/main.py`, the existing FastAPI routes, the agent implementation, `output/desk_tickets.html`, `output/harness.md`, and `AI_prompts.md`. Build on the existing backend rather than duplicating its functionality or rebuilding the agents.
> Build the frontend dashboard in `frontend/` using React, Vite, and TypeScript. I want it to feel like a polished, modern operations desk that someone would genuinely enjoy using, not a generic admin template. Use a thoughtful visual hierarchy, clear status indicators, well-designed cards and panels, and a layout that makes it easy to monitor tickets, follow agent activity, and review proposed actions.
> The dashboard should:
>
> * List all three tickets, showing their details and whether each is open or resolved.
> * Let me select a ticket and start the existing agent team on it through the Problem 7 backend.
> * Show what each agent is saying and doing while the ticket runs, including tool calls and relevant results. Refresh the event feed so I can follow the run without manually reloading the page.
> * Show a short summary of what each agent did once the run finishes.
> * Display the checking balance prominently and update it after an approved payment.
> * Let a human review and explicitly approve a proposed payment or purchase when one is available, using the existing backend approval route. Show the amount, purpose, relevant details, and approval status clearly. Never execute an action merely because a ticket was selected or an agent proposed it.
> * Show a ticket as resolved when the backend reports that it is resolved.
> * Handle loading states, empty states, errors, and unsuccessful API requests clearly so I can understand what is happening.
>
> Configure the frontend to call the backend at `http://localhost:8000`. Update the FastAPI CORS configuration to allow the Vite development origin, normally `http://localhost:5173`, so the browser can call the API. Do not weaken the backend’s approval safeguards or bypass its routes by accessing the database directly from the frontend.
> The dashboard should run with `npm run dev` from `frontend/`. Once it is ready, I should be able to open it in my browser, see the three tickets and current checking balance, select a ticket, watch agent activity, and review any proposed payment or purchase. If the current saved proposals do not contain an approvable action, show a helpful empty state rather than inventing a proposal or automatically making a paid agent run.
> Write `output/design.md` explaining the visual design, layout, how agent activity and ticket resolution are presented, how cash and approvals are displayed, and why these choices make the dashboard useful and distinctive.
> Update `output/harness.md` cumulatively with the frontend setup, important components, API routes used, and how to run the dashboard. Update `AI_prompts.md` with the actual prompt I used for Problem 8, preserving all previous entries and adding follow-ups only if I actually send them.
> Run the available frontend checks and tests, and verify the dashboard against the existing backend where possible. Use mocks or local checks when possible to avoid unnecessary Portkey calls. Do not run the agents live or spend Portkey credits just to populate the dashboard. Do not modify either database, clear or rewrite the audit trail, change the existing proposals, expose secrets, or start Problem 9.
> When finished, report what you built, which checks passed, how to start the backend and frontend, and any remaining limitations.

### Follow-up prompt

Why it was needed: the first Problem 8 prompt didn't ask for a final review against the assignment, and while checking the dashboard I accidentally stopped the user's Lecture 10 Vite server. This follow-up asked for all checks to be rerun, the docs to be completed, and the incident to be documented honestly with the restart command.

> I want to finish documenting Problem 8 before moving on.
>
> Please do a final review of the dashboard against both panels of the assignment. Verify that the React + Vite + TypeScript frontend lists all three tickets, lets me select and run a ticket, displays agent activity and summaries, reflects resolved status, supports human approval through the existing backend route, and displays the checking balance correctly. Confirm that the loading, error, and empty states work, and that the frontend uses the Problem 7 API rather than accessing the database directly.
>
> Please verify the frontend typecheck, lint, production build, and tests, along with the backend test suite. Check `output/design.md`, `output/harness.md`, and `AI_prompts.md` for completeness. Preserve all earlier problem documentation and record only prompts and follow-ups I actually sent.
>
> Also document the accidental stopping of the Lecture 10 Vite server honestly in the troubleshooting notes, including the original command needed to restart it. Do not restart it yourself, kill or modify any other processes, or use broad process-matching commands. I will decide when to restart it.
>
> Do not make Portkey calls, run agents live, modify either database, alter the audit trail or saved proposals, or start Problem 9. If you find a genuine documentation omission, fix it; otherwise leave the working code unchanged.
>
> Report the final test results, files changed, the exact commands to start the Homework 5 backend and frontend, and the command I can use to restart Lecture 10 when I want it back.

## Problem 9: Resolve the tickets

### Prompt

> I want to complete Problem 9: Resolve the tickets.
>
> Please inspect the existing project and the work completed in Problems 1–8 first, including the agent team, MCP server, backend API, React dashboard, `output/desk_tickets.html`, `output/proposed_resolutions.json`, `output/audit_trail.json`, and the existing documentation. Build on the current implementation rather than rebuilding it.
>
> Before running the agents, reset `data/campus_customs_new.db` to the original database values using the existing reset functionality. Do not modify `data/campus_customs.db`. Verify that the reset succeeded and record the starting checking balance from `cash_accounts`. Confirm that the backend and dashboard are working, and review the existing safety guardrails and approval workflow before proceeding.
>
> Then run all three tickets—#101, #102, and #103—through the React dashboard and existing backend, resolving each ticket through the agent team and the required human approval workflow. I want to observe the actual agent activity, delegations, MCP tool calls, proposals, and approvals. Do not mark tickets resolved unless the backend confirms that they are resolved through the intended workflow. If a ticket cannot be resolved safely, stop and report the blocker rather than inventing a successful outcome or bypassing a guardrail.
>
> For each ticket, record which agents actually worked on it, what each agent contributed, which delegations occurred, which MCP tools were used, the final status and outcome, and any human approvals. Keep the Expected sections in `output/desk_tickets.html` from Problem 6 unchanged, and fill in the Actual sections based on the real runs so I can compare what happened with what I originally expected.
>
> On the Cash tab in `output/desk_tickets.html`, document the starting checking balance, each ticket's actual cash impact and the reason for it, and the ending checking balance. Reconcile the arithmetic and verify that the ending balance matches `cash_accounts` in `data/campus_customs_new.db`. Do not assume a proposed payment or purchase changed cash; record only transactions that actually occurred.
>
> Save `output/resolved_tickets.json` with each ticket's ID, final status, short outcome, actual agent contributions, and any human approvals. Create `output/resolved_board.html` with a screenshot of the React dashboard for each resolved ticket, covering tickets #101, #102, and #103. Use actual screenshots and real outcomes; do not fabricate screenshots or mark an unresolved ticket as resolved.
>
> Append the actual runs to `output/audit_trail.json` without clearing, replacing, or rewriting existing entries. Finish `output/harness.md` so it comprehensively covers the database tables, MCP tools, five agents and their delegation boundaries, API routes, dashboard, safety rules, test results, and the final ticket and cash outcomes.
>
> Update `AI_prompts.md` with the actual prompt I used for Problem 9, preserving all earlier entries and adding follow-ups only if I actually send them.
>
> This problem requires real agent runs, so I understand that it will use Portkey credits. Minimize unnecessary model calls and do not rerun a ticket that has already completed successfully. Do not expose secrets, contact real customers or vendors, or perform any real-world transactions. All payments and purchases must remain within the local simulation and require explicit human approval. Never allow the checking balance to go negative.
>
> After completing the work, report the actual model-call count and token usage if available, the cash reconciliation, the status of all three tickets, the screenshots and files created, any errors or blockers, and the remaining limitations. Do not start Problem 10.

### Follow-up prompt

Why it was needed: the review before the paid runs found that tickets without a payment couldn't be resolved and that the known Problem 5 agent gaps were still present. This follow-up confirmed the fixes, the separate human-approved resolution step, and per-payment approval by the user before any Portkey spending.

> Yes, proceed with all three choices: fix the known Problem 5 agent gaps first, add a separate human-approved resolution action, and ask me for approval for each payment or purchase.
>
> Before making any paid Portkey calls, implement the fixes and resolution action, then rerun the full offline test suite. Make sure the resolution action requires my name and explicit confirmation, applies only to the latest valid run, is recorded in the audit trail, and never changes cash. Keep all payment and purchase approvals separate and wait for me to approve each one individually.
>
> Then continue Problem 9 from the reset state you already verified. Run tickets #101, #102, and #103, pausing whenever a payment or purchase needs my approval. Do not approve anything on my behalf. Verify every cash change against the working database and reconcile the starting and ending balances exactly.
>
> Complete the Actual sections in output/desk_tickets.html, save output/resolved_tickets.json and output/resolved_board.html, append the real run events to output/audit_trail.json, and finish output/harness.md. Update AI_prompts.md with the actual prompts and only the follow-ups I have sent. Preserve the original database, never contact real customers or vendors, and do not start Problem 10. If any ticket cannot be resolved safely or the agent proposals are inadequate, stop and explain the blocker rather than fabricating a resolution.

_Note: the user's individual approvals (#102 payment and resolution, #101 resolution, #103 resolution) were given as answers to the assistant's multiple-choice questions in chat, not as typed prompts, so they are recorded in `output/harness.md` and `output/resolved_tickets.json` rather than here._

### Follow-up prompt 2

Why it was needed: before Problem 10, the user asked for a final audit of every Problem 9 deliverable against the real database and audit trail. The audit found damaged dollar amounts in the outcome text and wording that overstated the agent fixes.

> Before starting Problem 10, please do a final Problem 9 audit. Do not make any Portkey calls, rerun agents, approve anything, or change the database.
>
> 1. Verify that output/resolved_tickets.json, output/resolved_board.html, output/desk_tickets.html, output/audit_trail.json, output/harness.md, and AI_prompts.md all agree with the actual final database and audit trail.
> 2. Reconcile the $3,400 starting checking balance to the $1,000 ending balance using the actual payment records. Confirm invoice 501 remains unpaid and that tickets #101, #102, and #103 are marked resolved.
> 3. Check that the 14 screenshots in output/screenshots/ are genuine screenshots of the actual dashboard states and that the resolved board links to the correct files.
> 4. Review the final limitations carefully. In particular, confirm that #101 was resolved without paying invoice 501, #103's restock was blocked because its cost was missing, and the proposed pricing fix did not actually solve that issue. Do not describe these as fixed.
> 5. Confirm that the original database is unchanged, the audit hash chain is intact, and all 78 backend and 23 frontend tests pass without altering real data.
> 6. Check that AI_prompts.md preserves the earlier Problems 1–8 entries and records only prompts and follow-ups I actually sent.
>
> Make documentation-only corrections if needed, preserving the original Expected plans and earlier problem sections. Report any discrepancy honestly. Do not start Problem 10.

### Follow-up prompt 3

Why it was needed: sent during the audit to make sure running the test suites could not alter the final Problem 9 data, and that anything that couldn't be verified safely would be reported as unverified.

> One additional safeguard for the final audit: when running the backend and frontend test suites, ensure they do not alter the actual final Problem 9 data. Use a temporary or test database wherever possible, and verify that the working database, payment records, ticket statuses, and audit trail are unchanged after testing.
>
> Do not make any Portkey calls, rerun agents, approve anything, reset either database, or change any actual Problem 9 data. If you cannot safely verify a requirement, report it as unverified rather than attempting a risky workaround.
>
> Please continue the audit from my previous prompt, make documentation-only corrections if needed, and do not start Problem 10.

_Note: the user's dashboard-troubleshooting request sent between Problem 9 and this audit is intentionally not logged, because it asked not to change the prompt log._


## Problem 10: Reflection

### Prompt

> I have finalized my Problem 10 reflection. Please save the reflection below in the Reflection tab of `output/desk_tickets.html`, following the Problem 10 instructions and the existing structure and styling of the dashboard.
>
> Use the five questions as the section headings, with my answer to each question under the corresponding heading. Preserve my wording and substance; make only minor formatting adjustments needed to fit the existing HTML. Do not add a separate overall-reflection section.
>
> Also update `output/harness.md` to record that Problem 10's reflection has been completed, if appropriate, while preserving all earlier sections and the original Expected plans.
>
> Update `AI_prompts.md` with the actual prompt I used for this Problem 10 save step. Do not invent follow-up prompts or alter earlier entries.
>
> Do not change either database, payment records, ticket statuses, proposals, the audit trail, or screenshots. Do not make Portkey calls, rerun agents, approve anything, or start Problem 11.
>
> After saving, verify that all five questions and their complete answers appear correctly in the Reflection tab, that the HTML remains valid, and that the Expected plans and earlier problem sections are unchanged. Report exactly which files you changed.
>
> Here is my final reflection to save:
>
> Problem 10: Reflection
>
> 1. How would I evaluate the performance of the agents on each ticket, and why?
>
> I would evaluate the agents on factual accuracy, safety, usefulness of their recommendations, and efficiency of coordination. Across the three tickets, the agents generally retrieved relevant information and respected the safety controls, but they were less consistent in translating that information into complete, actionable proposals.
>
> * Ticket #101 — Bulldog tee: The agents performed well on fact-finding and safety, but the outcome was incomplete. Inventory correctly identified that size S was out of stock and found Bulldog Print Co as a potential supplier with an approximately five-day lead time. Accounting also identified invoice 501, an overdue and unpaid invoice for $840. Customer Service drafted a reply without sending it, respecting the no-contact requirement. However, the team did not produce a payment proposal for invoice 501, even though my Expected plan called for reviewing whether it could be paid without making cash negative. The team also duplicated some work by reaching Inventory through multiple delegation paths. I approved resolving the ticket, but invoice 501 remained open and unpaid. I would therefore evaluate this run positively on safety and factual accuracy, but less positively on completeness and coordination.
> * Ticket #102 — Rent due: This was the strongest run because the agents produced a clear, actionable payment proposal supported by the available information. Facilities verified that $2,400 was due to Elm City Properties and that no rent payment had been recorded. Accounting projected that paying the rent would reduce checking from $3,400 to $1,000, leaving a $160 buffer if invoice 501 were also paid. I approved the rent payment, and the backend recorded it. However, Boss made a separate request to Accounting instead of relying entirely on the Facilities-to-Accounting handoff, as I had planned. Accounting also performed duplicate tool calls. The outcome was correct and safe, but the coordination could have been more efficient.
> * Ticket #103 — Bulk hoodies: The agents identified the inventory shortfall and supplier lead time, and Accounting calculated a list-price quote of $1,160 for 20 hoodies, with a stated unit cost of $22. However, the team did not produce a complete set of useful options. It did not offer the option of supplying eight size M hoodies and twelve size L hoodies, despite the available L inventory. More importantly, the restock proposal lacked the cost information required by the cash guardrail, so the proposed restock was blocked. The pricing guidance added before the run did not fix this problem. Blocking the incomplete proposal was the correct safety behavior, but the team still failed to provide an actionable restock recommendation. I approved resolving the ticket, but the 12-unit shortfall remained without a priced restock proposal. I would evaluate this run as safe but insufficiently useful.
>
> Overall, the human-approval process and programmatic guardrails worked as intended: the $2,400 rent payment required my approval, no other payment was made, and the unpriced restock was blocked. The main weaknesses were incomplete proposals and inefficient coordination rather than unsafe execution.
>
> 2. How did the actual outcome for each ticket compare with my Expected plan?
>
> * Ticket #101: My Expected plan was to route the ticket through Customer Service first, then Inventory, and have Accounting review invoice 501 and whether paying it would leave cash non-negative. I expected three delegations, a draft customer reply, a substitute offer based on available sizes, and a payment proposal for the $840 invoice if the cash check supported it. I also expected no new restock order.
> In the actual run, Boss contacted Inventory and Customer Service in parallel, after which Customer Service contacted Inventory and Accounting. The team made four delegations instead of three. It drafted a reply, but did not create a separate substitute-offer proposal or a payment proposal for invoice 501. It correctly avoided creating a restock order. The most important difference was that the overdue invoice was identified but not acted upon. The ticket was resolved with my approval even though the invoice remained unpaid.
> * Ticket #102: My Expected plan was for Boss to contact Facilities first, followed by Accounting, with two delegations and no separate parallel request from Boss to Accounting. I expected a $2,400 payment proposal to Elm City Properties, pending approval, and a warning that paying the rent would leave only a $160 buffer if invoice 501 were also paid.
> The actual run produced the correct rent amount, payee, and cash projection, and the payment was recorded after I approved it. However, there were three delegations rather than two because Boss also contacted Accounting directly. This was the closest match to my plan in terms of the business outcome, although the routing instructions were not followed completely.
> * Ticket #103: My Expected plan was for Customer Service to coordinate with Inventory and Accounting, without Boss separately contacting either of them. I expected three delegations and several options: fulfilling the eight size M hoodies currently available, mixing eight size M with twelve size L, waiting for all 20 size M hoodies to arrive, and considering discounts in the 5–15% range. I also anticipated that a restock proposal without a cost would be blocked by the cash guardrail.
> In the actual run, Boss contacted Customer Service, Accounting, and Inventory in parallel, resulting in four delegations. The agents identified the shortage and lead time, but did not provide the mixed-size option or a priced partial-fill option. They considered a 5% discount, but the restock proposal lacked an amount and was blocked. The attempted pricing fix did not resolve the issue. Thus, my plan correctly anticipated the safety failure mode, but the actual result fell short of the useful alternatives and complete proposal I wanted.
>
> Comparing Expected with Actual showed me that agents can retrieve the right facts without necessarily following the intended workflow or producing the intended decision. Ticket #102 demonstrates that the system can generate and execute a safe payment after approval. Tickets #101 and #103 demonstrate why I need to evaluate the completeness of the underlying resolution, not just the final status.
>
> 3. What would have been simpler with one agent and tools, and why?
>
> For these three tickets, a single agent with access to the relevant tools could plausibly have completed the work with fewer handoffs and less duplicated effort. The tasks largely involved checking inventory, suppliers, invoices, rent, cash balances, and pricing, then preparing recommendations for my approval.
>
> * Fewer duplicate delegations: Inventory was reached through duplicate paths on ticket #101, while Accounting was contacted more than once on tickets #102 and #103. The actual runs used 11 delegations against eight planned.
> * Better continuity of information: A single agent could retain the information it had already gathered. For example, after obtaining the rent amount and checking the cash balance, it could carry those facts directly into its payment proposal instead of relying on a handoff that might omit relevant information.
> * Simpler recommendations: One agent could present a consolidated recommendation with the amount, payee, projected remaining balance, and any unresolved invoice, rather than coordinating separate responses from multiple agents.
> * Safety would still be enforceable: Human approval, cash validation, and restrictions against contacting customers or vendors without authorization are enforced through the application and its tools. These safeguards would still apply in a single-agent design.
>
> This is a reasoned hypothesis, not a measured result, because I did not run a single-agent version as a controlled comparison. Multiple agents may still be valuable for larger workflows or when different roles need different tool permissions. However, for these relatively small tickets, one agent with well-defined tools and enforced guardrails would likely be simpler to coordinate and could reduce unnecessary model requests and token use.
>
> 4. What are three new Campus Customs problems the agent team could solve with the tools already built?
>
> * Investigating overdue invoices and preparing payment recommendations: The team could check an invoice's status, review recorded payments, and project the cash balance after a proposed payment. For example, it could revisit invoice 501, which remains open and unpaid, and determine whether paying $840 would leave enough cash. With a current checking balance of $1,000, the projected balance after that payment would be $160. The team could prepare a recommendation for human approval rather than paying automatically.
> * Answering stock availability and supplier lead-time questions: If a customer asked about another product, such as a Crest Mug, Inventory could check stock and search the vendor list for a potential supplier and lead time. Customer Service could use those facts to draft a response without contacting the customer. This would help the shop respond more consistently to availability questions while keeping external communication under human control.
> * Preparing bulk-order quotes and checking discount limits: If a club wanted to purchase 50 caps, Inventory and Accounting could use the existing stock and bulk-quote tools to assess availability, calculate pricing, and evaluate whether proposed discounts remain above cost. Customer Service could then prepare a quote for review. The team could support the decision and draft the response, although it should not promise a discount or send the quote without authorization.
>
> These examples use existing lookup and quoting capabilities. They do not assume that the system can automatically purchase stock, reserve inventory, receive customer payments, or send messages.
>
> 5. What are three new Campus Customs problems the agent team could not solve with the current tools, and what additional tools and agents would be needed?
>
> * Creating and managing priced restock orders: Ticket #103 exposed this limitation directly. The team identified that 12 size M hoodies were missing, but it could not produce a complete restock proposal with the required cost information. The existing pricing data describes the shop's unit cost; it does not provide a vendor-specific quote for the requested quantity. The proposed pricing guidance did not solve the problem, and the cash guardrail correctly blocked the incomplete proposal.
> To address this, I would add a vendor price list or quotation system and a tool to retrieve vendor quotes for a particular product and quantity. I would also add a Purchasing agent and a human-approved purchase-order workflow. A receiving tool would be needed to update inventory when a shipment actually arrives. These additions would let the system distinguish between identifying a shortage, obtaining a reliable supplier price, proposing a purchase, and recording the receipt of goods.
> * Managing customer orders from selection through payment and fulfilment: The current system can check stock and draft customer replies, but it does not have a complete order-management workflow. For example, it cannot reliably reserve eight hoodies, record a customer's chosen sizes, accept and record customer payment, and track the order through fulfilment using the tools currently built.
> This would require order and receipt records, tools to reserve stock and record a sale, and an Orders agent to coordinate the process. A human-approved communication workflow would also be needed before sending confirmations or other messages. These additions would connect customer requests to actual inventory commitments and recorded revenue instead of stopping at a recommendation or draft reply.
> * Managing new tickets and ongoing ticket follow-up: The current workflow can inspect existing tickets and mark a ticket resolved with human approval, but it does not provide a complete way to create new tickets, update their notes, record customer responses, or reopen a case when a problem remains outstanding. For example, if a customer responded to a draft or reported that an order had still not arrived, the team would need a way to record that development and continue the case.
> I would add tools to create tickets, update ticket details, and add notes, along with intermediate statuses such as “waiting on customer” or “waiting on supplier.” An Intake agent could triage incoming requests and route them to the appropriate team. This would make the system useful for ongoing operations rather than only processing a fixed set of existing tickets.
