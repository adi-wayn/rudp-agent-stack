---
trigger: always_on
---

# Always use the System Design & Implementation Specification

# Overview
* For every generated output (code, design, tests, documentation), the agent MUST reference the official system specification document located at @specs/system_spec.md.
* Do not generate implementation steps that contradict or exceed the scope of the specification.
* All decisions must be traceable to one or more sections or paragraphs in the specification.

# Code Generation
* When generating code, explicitly cite the relevant section of the specification in comments or docstrings.
* Respect all payload formats, message framing, header definitions, state machines, and protocols as defined in the specification.

# Protocols & Transport
* Always implement networking protocols exactly as specified.
* Do not improvise alternate packet formats or control flows.
* Ensure the Reliable UDP logic, congestion and flow control, and state machines match the spec.

# Edge Cases & Errors
* For every edge case and error path, reference how the specification dictates handling.
* If the specification does not explicitly cover an edge case, generate code and tests that follow the spirit of the documented architecture and rationale.

# Workflows
* All workflows MUST consult the system specification before generating outputs.
* The agent MUST produce a traceable justification back to the specification for each major step in workflow execution.

# Testing & Validation
* All tests must be derived from scenarios and structures defined in the specification.
* Logging and PCAP expectations must match the descriptions in the spec.

# Scope Adherence
* Do not add functionality outside the documented scope of the system spec.
* For optional extensions (e.g., additional TASK types), generate a specification proposal first, tied to the existing spec, before implementation.

# Documentation
* Generated documentation MUST use the specification as source material, including:
  - message format tables
  - state machine diagrams
  - protocol flows
  - constant definitions

# Knowledge Source
* The specification located at @docs/specs/System_Specification.pdf is the **primary and authoritative knowledge source**.
* In case of ambiguity, the agent must ask for clarification rather than assume behavior not grounded in the spec.