---
description:  Implement client-side upload logic (PUT_META + chunked PUT_CHUNK) and ensure strict compatibility with server implementation.
---

# Workflow: client_day3_upload_flow

description: Implement client-side upload logic (PUT_META + chunked PUT_CHUNK) and ensure strict compatibility with server implementation.

goal:
Implement deterministic upload session flow on the client side and integrate it with transport abstraction and action selector.

steps:

1. Confirm Server Contract:

   * Verify PUT_META response format (upload_id location).
   * Verify PUT_CHUNK payload schema (upload_id, offset, chunk_len + raw bytes).
   * Confirm envelope format (12-byte header, big-endian).
   * Confirm upload completion rule (LAST_CHUNK flag or offset == total_size).
   * Confirm max retries policy.

2. Implement Client Action Selector:

   * Add upload action to main entry.
   * Dispatch to upload_file(local_path, remote_filename, overwrite).
   * Keep transport layer unaware of application logic.

3. Implement Upload Initialization (U_INIT):

   * Validate local file exists.
   * Read total_size.
   * Ensure total_size ≤ MAX_FILE_SIZE (1 MiB).
   * Define safe chunk_size.
   * Initialize:

     * request_id generator
     * offset = 0
     * retry counters

4. Implement PUT_META Sender:

   * Build JSON payload:

     * filename
     * total_size
     * overwrite
     * optional_hash (null if unused)
   * Wrap with envelope (opcode = PUT_META).
   * Send via transport.
   * Wait for response.
   * Validate status_code.
   * Extract upload_id.
   * Retry on timeout (max 5).

5. Implement Chunked PUT_CHUNK Loop:

   * While offset < total_size:

     * Read chunk_data.
     * chunk_len = len(chunk_data).
     * Build JSON metadata:

       * upload_id
       * offset
       * chunk_len
     * Append raw chunk bytes.
     * Wrap in envelope (opcode = PUT_CHUNK).
     * Send.
     * Wait for ACK.
     * On success:

       * offset += chunk_len.
     * On timeout:

       * Resend same chunk (same offset).
       * Increment retry counter.
     * Abort if retries exceed limit.

6. Enforce Offset Discipline:

   * Offset measured in bytes (not chunk index).
   * Do not advance offset before confirmation.
   * Ensure resend uses identical offset and data.

7. Handle Error Responses:

   * 403 → abort (policy violation).
   * 409 → abort (conflict).
   * 413 → abort (file too large).
   * 500 → abort (server error).

8. Completion Detection:

   * Upload completes when offset == total_size.
   * Close transport gracefully.
   * Log summary.

9. Logging:

   * PUT_META:

     * request_id
     * status_code
   * PUT_CHUNK:

     * upload_id
     * offset
     * chunk_len
     * retries
   * Final summary:

     * total_chunks
     * total_retries
     * duration

10. Integration Checks:

* Confirm compatibility with server upload session behavior.
* Confirm envelope framing works correctly in TCP.
* Confirm no duplicate chunk corruption.

tests:

* Successful full upload (small file).
* Successful full upload (larger file ≤ 1 MiB).
* Timeout retry on PUT_META.
* Timeout retry on PUT_CHUNK.
* Duplicate chunk resend.
* Oversized file rejection.
* Server-side error response handling.

definition_of_done:

* Client upload state machine works end-to-end.
* PUT_META and PUT_CHUNK fully compatible with server.
* Offset handling deterministic and safe.
* Retry mechanism functional.
* No duplicate chunk corruption.
* All upload tests pass.