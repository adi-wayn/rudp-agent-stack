---
description: Implement the core Agent Server pipeline (no file uploads, no tasks).
---

# Workflow: app_server_day2_core_pipeline
description: Implement the core Agent Server pipeline (no file uploads, no tasks).

goal:
Build a production-correct application pipeline supporting LIST only.

steps:

1. Read system specification:
   - Application message format
   - Header fields (12B)
   - Error handling rules
   - Policy and idempotency requirements

2. Implement RequestContext:
   - Parse header + payload
   - Validate version
   - Validate payload_len <= MAX_PAYLOAD_LEN
   - Store opcode, flags, request_id

3. Implement PolicyGuard:
   - Enforce sandbox root directory
   - Enforce payload size limits
   - Reject invalid paths

4. Implement IdempotencyCache:
   - Key = (client_id, request_id, opcode)
   - TTL-based cache
   - Return cached response if duplicate request_id

5. Implement Dispatcher:
   - Map opcode → handler function
   - Unknown opcode → structured error response

6. Implement LIST handler only:
   - Read sandbox directory
   - Return structured payload (JSON recommended)
   - Use standard response envelope

7. Wire pipeline:
   Transport → AgentServer → Dispatcher → ResponseBuilder → Transport

8. Logging:
   - request_id
   - opcode
   - payload_len
   - status_code
   - processing_time_ms

9. Tests:
   - LIST success
   - Unknown opcode
   - Idempotency repeat request
   - Invalid payload_len rejection

definition_of_done:
- LIST works end-to-end
- Idempotency functional
- PolicyGuard active
- All tests pass
- compileall clean