---
description: Implement TASK client-side support according to System Specification with strict architectural separation.
---

# Workflow: client_day5_task_support
description: Implement TASK client-side support according to System Specification with strict architectural separation.

goal:
Enable client to send TASK requests, parse responses, and handle inline vs artifact results
while preserving clean architecture, separation of concerns, and transport-agnostic design.

---

architectural_principles:

1. Separation of Concerns:
   - TaskHandler is responsible for "WHAT to send"
   - AgentClient is responsible for "HOW to send"
   - Transport is responsible only for raw byte transmission

2. Transport Agnostic Design:
   - TASK logic must not depend on TCP or RUDP specifics
   - No socket-level logic inside handlers
   - Same AgentClient API must work over both transports

3. Single Responsibility Principle:
   - TaskHandler → builds logical payload
   - AgentClient → builds envelope, manages request_id, parses responses
   - Artifact logic → reuse GET mechanism, no protocol duplication

4. No Protocol Duplication:
   - All envelope encoding/decoding centralized in AgentClient
   - Handlers must never compute payload_len, flags, or headers

5. Server-Driven Result Policy:
   - Server decides inline vs artifact
   - Client reacts dynamically
   - Client must not assume result type

---

steps:

1. Read Specification:
   - Application Envelope structure (version, opcode, flags, request_id, payload_len, payload)
   - OP_TASK and OP_TASK_RESP
   - Artifact response policy
   - MAX_PAYLOAD constraints (important for RUDP)

2. Validate Architecture Boundaries:
   - No protocol logic inside transport layer
   - No socket access inside TaskHandler
   - AgentClient is the only component allowed to:
     - Generate request_id
     - Encode/decode envelope
     - Parse opcode and flags

3. Implement TASK Payload Construction (TaskHandler):
   - Build logical JSON payload:
     - task_type
     - input_file
     - query
     - out_file
     - options (if applicable)
   - Validate required fields
   - Call AgentClient.request(OP_TASK, payload_dict)

4. Implement AgentClient TASK Request Flow:
   - Auto-generate request_id
   - JSON encode payload
   - Build envelope
   - Send via selected transport
   - Receive response
   - Decode envelope
   - Return structured response object

5. Implement Response Parsing Logic:
   - Validate opcode == OP_TASK_RESP
   - Validate request_id correlation
   - Parse payload JSON
   - Check status field
   - Raise logical error if needed

6. Inline Result Handling:
   - If "result" exists:
     - Return result immediately
     - No additional network calls
   - Maintain clean separation (no extra protocol logic here)

7. Artifact Handling:
   - If "artifact_file" exists:
     - Use AgentClient.request(OP_GET, ...)
     - Retrieve file bytes
     - Save locally
     - Return local file path
   - Must reuse GET logic (no duplicated protocol implementation)

8. Error Handling:
   - status != 200
   - Missing fields
   - GET failure after TASK success
   - Protocol mismatch (unexpected opcode)
   - Oversized payload scenarios

9. Logging (Application-Level):
   - request_id
   - task_type
   - status
   - inline vs artifact
   - artifact size (if applicable)

10. Validation Tests:
   - Small TASK → inline result
   - Large TASK → artifact + GET
   - Invalid TASK input
   - TCP transport
   - RUDP transport
   - request_id correctness

---

definition_of_done:
- TASK requests built correctly
- AgentClient handles all protocol-level concerns
- TaskHandler contains no envelope logic
- Inline results handled properly
- Artifact flow triggers GET automatically
- Works identically over TCP and RUDP
- Architecture remains modular and maintainable
- No violation of separation between Application and Transport layers
