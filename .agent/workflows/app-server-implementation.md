---
description: Implement the Agent-based Application Server.
---

# Workflow: app_server_implementation
description: Implement the Agent-based Application Server.

steps:
1. Read application message specification.
2. Generate request parser using defined binary header and payload schemas.
3. Implement rule-based planner mapping tasks to handler functions.
4. Define handlers for PUT_META, PUT_CHUNK, GET, APPEND, LIST.
5. Implement TASK handlers: SEARCH_REPORT, FILTER_LINES, HASH_AND_STORE.
6. Integrate idempotency cache and upload session tracker.
7. Add policy guard enforcement (sandbox, size limits).
8. Wire application logic to the Transport interface.
9. Create logging hooks per specification.
10. Create unit/integration tests for all opcodes and task flows.