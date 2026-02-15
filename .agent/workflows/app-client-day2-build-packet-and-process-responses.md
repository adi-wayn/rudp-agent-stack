---
description:  Implement the Day-2 Client task — build application packets (envelope) and correctly process server responses over the existing TCP transport.
---

# Workflow: app_client_day2_build_packet_and_process_responses
description: Implement the Day-2 Client task — build application packets (envelope) and correctly process server responses over the existing TCP transport.

goal:
Given the Day-1 TCP transport/framing baseline, produce a production-correct client-side request/response layer:
- build a valid application envelope packet
- send it via TCP
- receive + parse + validate the response
- map errors consistently
(Functional validation can be done using LIST as the single opcode for today.)

steps:

1. Re-read the System Specification contracts (client-facing):
   - Fixed 12B application header format (big-endian)
   - Opcode numeric definitions (LIST=0x05 recommended for validation)
   - Response requirements: request_id + status_code + optional message/payload
   - TCP framing rule: read exactly 12 bytes, then read exactly payload_length bytes

2. Define the Client Request/Response API surface:
   - send_request(opcode, flags, payload_obj_or_bytes) -> Response
   - Response structure should include:
       request_id, status_code, message(optional), payload(optional), raw_payload_len

3. Implement RequestIdManager (client-side):
   - Generate unique 32-bit request_id per request
   - Keep a pending map:
       pending[request_id] = { opcode, send_ts, retries }
   - Never reuse request_id for a different logical request
   - On retransmission (if used): reuse the SAME request_id

4. Implement EnvelopeBuilder (packet construction):
   - Inputs: version=1, opcode, flags, reserved=0, request_id, payload_bytes
   - Compute payload_length = len(payload_bytes)
   - Encode header fields big-endian into a 12-byte header:
       [version|opcode|flags|reserved|request_id(4)|payload_length(4)]
   - Output packet = header + payload_bytes
   - Validation:
       - header length == 12
       - payload_length matches actual payload size

5. Implement Payload Encoder (application-level payload):
   - If payload is JSON object:
       - encode as UTF-8 JSON bytes
   - If payload is bytes (future-proof for chunking ops):
       - use raw bytes as-is
   - For Day-2 validation, use LIST payload:
       - {}  (valid minimal)
       - or {"directory":"", "recursive":false}

6. Use the existing TCP transport (Day-1) with strict framing:
   - Send the full packet bytes (single write)
   - Receive response using framing logic:
       a) read exactly 12 bytes (response header)
       b) parse payload_length
       c) read exactly payload_length bytes (response payload)
   - Never parse JSON until the full payload has been assembled

7. Implement ResponseParser + ResponseValidator:
   - Parse response header (version/opcode/flags/request_id/payload_length)
   - Parse response payload:
       - If payload is JSON: decode UTF-8 and load JSON
   - Validate:
       - response.request_id == sent request_id
       - response.version == 1 (or supported)
       - payload_length correctness (received bytes count)
   - Extract:
       - status_code (required)
       - message (optional)
       - payload (optional)

8. Implement Status Code Mapping (client behavior):
   - 200/201: success path
   - 400: bad request → surface as client/protocol error
   - 403: forbidden (policy guard) → surface as access/path error
   - 404: not found → surface as missing resource
   - 409: conflict → surface as idempotency/collision style error
   - 413: payload too large → surface as size limit error
   - 500: server error → surface as remote failure
   - Ensure errors are returned in a consistent, structured way (not raw prints)

9. Add Minimal Observability (required debugging hooks):
   - Log per request:
       request_id, opcode, payload_len, send_ts
   - Log per response:
       request_id, status_code, response_len, rtt_ms
   - On validation failure:
       include a short reason (e.g., "request_id mismatch", "short read", "bad json")

10. Day-2 Validation (use LIST as the single functional check):
   - Positive:
       - Send LIST with {} and confirm:
           status_code=200, request_id match, payload parses
   - Negative (protocol correctness, not feature expansion):
       - Send malformed JSON payload → expect 400
       - Send directory=".." → expect 403
   - Keep these as simple scripted runs (one command / one test function)

definition_of_done:
- Client can build a correct 12B envelope + payload and send it over TCP
- Client can receive responses using strict framing and parse them correctly
- request_id is generated, tracked, and validated against responses
- status_code mapping is consistent and structured
- LIST works as the proof-of-life validation (one opcode is enough for Day-2)
- Logs show request_id/opcode/payload_len/status_code/rtt_ms
- compileall clean
