---
description: Implement GET, LIST, APPEND client calls + response parsing according to System Specification.
---

# Workflow: agent_client_day4_file_operations
description: Implement GET, LIST, APPEND client calls + response parsing according to System Specification.

goal:
Complete client-side application layer support for file operations over TCP/RUDP.

steps:

1. Implement LIST call:
   - Build optional JSON payload (directory, recursive)
   - If listing root → payload_length = 0
   - Build header with opcode 0x05
   - Send via transport
   - Receive full response (header + payload)
   - Validate status_code
   - Decode JSON payload
   - Return list of file metadata objects

2. Implement GET call:
   - Build JSON payload { "filename": "<name>" }
   - Build header with opcode 0x03
   - Send request
   - Receive full response
   - Validate status_code
   - If success → return raw payload bytes
   - If error → decode JSON error and return structured error

3. Implement APPEND call:
   - Build metadata JSON { "filename": "<name>" }
   - Concatenate metadata + raw data bytes
   - Calculate correct payload_length
   - Build header with opcode 0x04
   - Send request
   - Receive response
   - Validate status_code
   - Return confirmation

4. Implement unified response parsing:
   - Read exactly 12-byte header
   - Extract version, opcode, request_id, payload_length
   - Read exactly payload_length bytes
   - Match request_id with sent request
   - Route parsing based on operation type
   - Do not assume payload is always JSON

5. Error handling:
   - 403 → Forbidden (sandbox violation)
   - 404 → File not found
   - 409 → Conflict
   - 413 → Payload too large
   - Non-200 responses must not crash client

6. Idempotency handling:
   - If retry required (timeout), reuse same request_id
   - APPEND must not duplicate data on retransmission

7. Transport independence:
   - No modification to TCP or RUDP layer
   - Client must work identically over both transports
   - Handle TCP partial reads correctly

8. Tests:
   - LIST root directory
   - LIST recursive
   - GET existing file
   - GET missing file (404)
   - APPEND small data
   - Verify append via GET
   - Retry scenario (idempotency check)

definition_of_done:
- Client supports LIST, GET, APPEND
- Proper header framing implemented
- Response parsing robust
- Correct status handling
- Works over TCP and RUDP
- No transport-layer modifications
- Fully aligned with System Specification
