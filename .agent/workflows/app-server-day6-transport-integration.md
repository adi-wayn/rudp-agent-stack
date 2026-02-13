---
description: Prepare Agent Server for Transport abstraction (TCP + RUDP).
---

# Workflow: app_server_day6_transport_integration
description: Prepare Agent Server for Transport abstraction (TCP + RUDP).

goal:
Make application layer transport-agnostic.

steps:

1. Ensure AgentServer receives:
   - raw message bytes
   - returns raw response bytes

2. Remove TCP-specific assumptions.
3. Confirm compatibility with RUDP fragmentation/reassembly.
4. Validate response builder independent of transport.
5. Integration test with TCP before RUDP.

definition_of_done:
- AgentServer works with any Transport interface
- No transport-specific logic in application layer