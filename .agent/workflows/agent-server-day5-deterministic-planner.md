---
description: Implement a deterministic Planner that builds execution plans for TASK operations, decides memory vs streaming and inline vs artifact output, and delegates execution to the ToolDispatcher with full idempotency support.
---

Workflow: agent_server_day5_deterministic_planner

description:
Implement a deterministic rule-based Planner component for the Agent Server. The Planner must build execution plans for TASK operations (SEARCH_REPORT, FILTER_LINES, HASH_AND_STORE), support streaming vs memory mode decisions, enforce output policy (inline vs artifact), and integrate with the existing pipeline and idempotency mechanism.

goal:
Transform the TASK handler into a deterministic Agent-like execution engine where:

Planner builds a structured execution plan.

ToolDispatcher executes plan steps.

Optional plan artifact can be generated.

Side-effects are idempotent.

No transport-layer modifications.

Phase 1 — Architectural Refactor (Pipeline Integration)
1. Insert Planner Stage into Pipeline

Modify TASK opcode handling flow:

decode
→ validate
→ policy
→ idempotency_lookup
→ planner.build_plan(...)
→ tool_dispatcher.execute(plan)
→ build_response
→ cache_response
→ send_response


Constraints:

Replay via idempotency MUST bypass planner + execution.

Planner MUST NOT perform I/O directly.

Planner MUST be deterministic.

Phase 2 — Planner Core Design
2. Define Planner Interface

Create component:

planner.build_plan(task_payload, context) -> Plan


Context includes:

client_id

request_id

file_size (stat result)

system limits (MAX_FILE_SIZE, STREAM_THRESHOLD, MAX_INLINE_SIZE)

Plan object MUST include:

plan_id (deterministic hash of task + options)

steps (ordered list)

execution_mode ("memory" | "stream")

output_policy ("inline" | "artifact" | "dynamic")

side_effects (boolean)

explain_summary (string)

optional_plan_artifact (boolean)

Phase 3 — Plan Step Schema
3. Define Step Structure

Each step MUST contain:

{
  tool: string,
  args: dict,
  produces: string,
  consumes: string | null
}


Allowed tools:

READ_FILE

STREAM_READ

SEARCH_LINES

FILTER_LINES

HASH_SHA256

BUILD_REPORT

WRITE_FILE

WRITE_ARTIFACT

Planner MUST NOT execute tools.
Planner MUST only describe them.

Phase 4 — Deterministic Decision Rules
4. Execution Mode Rule
if file_size <= STREAM_THRESHOLD (e.g., 256KB):
    execution_mode = "memory"
else:
    execution_mode = "stream"


This decision MUST be deterministic.

5. Output Policy Rule

Planner MUST enforce:

Inline allowed only if result <= 64KB

Otherwise artifact required

Since result size may be unknown:

Plan MUST include caps (max_lines / max_bytes)

Plan MUST include fallback to artifact write

6. Artifact Naming Rule (Critical for Idempotency)

If plan creates files or artifacts:

Artifact path MUST be deterministic:

artifacts/{client_id}/{request_id}_result.json
artifacts/{client_id}/{request_id}_plan.json


No random naming allowed.

Phase 5 — Task Templates
7. SEARCH_REPORT Template

Steps:

READ_FILE or STREAM_READ

SEARCH_LINES (query, caps)

BUILD_REPORT

OUTPUT_DECISION

Inline if small

Else WRITE_ARTIFACT

Side effects:

Only if artifact written

8. FILTER_LINES Template

Case A — out_file provided:

STREAM_READ

FILTER_LINES

WRITE_FILE(out_file)

BUILD_REPORT

Side effects = true

Case B — no out_file:

STREAM_READ

FILTER_LINES

OUTPUT_DECISION

Inline if small

Else WRITE_ARTIFACT

9. HASH_AND_STORE Template

STREAM_READ

HASH_SHA256

WRITE_FILE(hash_output)

BUILD_REPORT

Side effects = true

Phase 6 — Optional Plan Artifact

If:

options.return_plan == true


Planner MUST add:

WRITE_ARTIFACT(plan.json)


Plan artifact MUST include:

plan_id

steps

decisions

execution_mode

output_policy

limits applied

Phase 7 — Tool Dispatcher Integration
10. Execute Plan Sequentially

ToolDispatcher MUST:

Execute steps in order

Pass produced outputs to next steps

Respect execution_mode

Handle fallback to artifact if size exceeds limit

Return final response payload

Phase 8 — Idempotency Enforcement
11. Before Execution

If request_id exists in idempotency cache:

Return cached response immediately.

12. After Execution

If plan.side_effects == true:

Cache full response including artifact paths.

Cache TTL: 120 seconds (as defined in system spec).

Phase 9 — Unit Tests (Planner-Level)

Create isolated tests for planner:

Correct template selected per task_type

Correct execution_mode decision based on file size

Correct output_policy determination

Correct artifact path determinism

Correct side_effects flag

Planner tests MUST NOT perform file I/O.

Phase 10 — Integration Tests (Handler-Level)

For each TASK:

Test:

Small file → inline response

Large file → artifact response

With out_file → file created once

Duplicate request_id → no re-execution

options.return_plan → plan artifact generated

Constraints

No modifications to Transport layer.

No modifications to framing.

No stochastic logic.

No random artifact names.

No tool execution inside Planner.

All decisions must be reproducible given same input and state.

Deliverables

planner module

updated TASK handler

updated ToolDispatcher

unit tests (planner)

integration tests (TASK)

updated state diagram in documentation