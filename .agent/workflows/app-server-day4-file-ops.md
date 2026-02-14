---
description: Implement GET, APPEND, and refine LIST.
---

# Workflow: app_server_day4_file_operations
description: Implement GET, APPEND, and refine LIST.

goal:
Complete basic file operations layer.

steps:

1. Implement GET handler:
   - Validate file exists
   - Enforce sandbox
   - Stream file or return full payload (<= MAX_FILE_SIZE)

2. Implement APPEND handler:
   - Validate file exists
   - Append safely
   - Return updated size

3. Refine LIST:
   - Include metadata (size, timestamp optional)

4. Integrate error handling:
   - File not found → 404
   - Permission violation → 403
   - Payload too large → 413

5. Idempotency:
   - APPEND must not duplicate on repeated request_id

6. Tests:
   - GET success
   - GET missing file
   - APPEND success
   - APPEND duplicate idempotency
   - LIST consistency

definition_of_done:
- File server functional over TCP
- Correct status codes
- Idempotency preserved