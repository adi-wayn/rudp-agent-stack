---
description: Implement file upload logic (PUT_META + PUT_CHUNK).
---

# Workflow: app_server_day3_upload_sessions
description: Implement file upload logic (PUT_META + PUT_CHUNK).

goal:
Add upload session state machine and integrate with core pipeline.

steps:

1. Read Upload Session State Machine diagram.
2. Implement UploadSessionManager:
   - Create session on PUT_META
   - Track filename, total_size, received_chunks
   - Maintain session timeout

3. Implement PUT_META handler:
   - Validate filename (PolicyGuard)
   - Validate total_size <= MAX_FILE_SIZE
   - Create session
   - Return ACK

4. Implement PUT_CHUNK handler:
   - Validate session exists
   - Validate offset correctness
   - Prevent duplicate chunk overwrite
   - Append to file safely
   - Detect completion

5. Integrate with Idempotency:
   - Repeated PUT_CHUNK with same request_id returns cached result

6. Logging:
   - session_id
   - offset
   - bytes_written
   - completion status

7. Tests:
   - Successful full upload
   - Duplicate chunk
   - Missing session
   - Out-of-order offset
   - Oversized file rejection

definition_of_done:
- Upload state machine works
- Partial upload persists correctly
- Duplicate protection works
- All upload tests pass