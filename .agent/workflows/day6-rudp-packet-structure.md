---
description: Define and formalize the RUDP packet structure exactly per System Specification: fixed header (seq, ack, flags, rwnd, checksum) and DATA layout including msg_id=request_id and offset for reassembly. No new fields. No application changes.
---

# Workflow: day6_rudp_packet_structure
description: >
  Define and freeze the RUDP packet structure exactly as specified in System Specification,
  including fixed header fields and minimal data-packet reassembly fields (msg_id=request_id, offset).
  Do NOT modify application envelope (12B header) or application semantics.

goal:
  Produce a formal packet layout spec for RUDP (DATA + ACK-only) and a packing/unpacking contract
  that can be implemented consistently on client and server.

inputs:
  - System Specification.md (Transport Layer I + Addendum 8.16.4/8.16.1/8.16.2)
  - rudp-agent-stack-daily.csv (Day 6 tasks)

constraints:
  - Must use ONLY information in the provided documents.
  - Must NOT add new header fields beyond the fixed-width RUDP header specified.
  - Reassembly identifier MUST be msg_id = request_id.
  - Receiver MUST buffer segments by (msg_id, offset).
  - ACK is cumulative; receiver sends ACK for every valid packet; duplicates trigger duplicate ACK.
  - rwnd is in "segments" and advertised in every outgoing ACK.
  - Keep TCP baseline unchanged; RUDP must remain transport-agnostic relative to application layer.

deliverables:
  1) "RUDP Packet Format Spec" markdown section (ready to paste into project PDF):
     - Fixed header field table with sizes and meanings
     - DATA packet layout (header + [msg_id|offset] + segment bytes)
     - ACK-only packet layout (header only)
     - Encoding rules: big-endian vs stated if specified; checksum presence; flags set semantics
  2) "Serialization Contract" (no code):
     - pack(header_fields) -> bytes
     - unpack(bytes) -> header_fields + optional reassembly fields + payload
     - validation rules: checksum fail => drop; seq relation => ack behavior
  3) "Wireshark Expectations" notes:
     - which bytes correspond to seq/ack/flags/rwnd/checksum
     - expected retransmission behavior visible as repeated seq numbers (semantic, not implementation)

steps:
  - step: Locate authoritative sections in System Specification
    actions:
      - Extract RUDP Fixed Header definition (seq/ack/flags/rwnd/checksum) and sizes.
      - Extract ACK semantics (cumulative ACK, ACK each valid packet, duplicate ACK).
      - Extract rwnd semantics (segments, advertised in every ACK, watermark behavior mention).
      - Extract reassembly identifier rule: msg_id=request_id and buffering by (msg_id, offset).
    acceptance_criteria:
      - Each extracted rule is traceable to a specific subsection in the spec.

  - step: Freeze fixed header layout
    actions:
      - Produce a header table with exact bit-widths: 32/32/8/16/16.
      - Define field order as it will appear "on the wire" (consistent across client/server).
      - Define flags vocabulary limited to: SYN, ACK, FIN, RST (as specified).
    acceptance_criteria:
      - Header size computed and stated.
      - No extra header fields introduced.

  - step: Define DATA packet payload reassembly fields (minimal)
    actions:
      - Add a reassembly prefix within payload that contains exactly:
        - msg_id (= request_id)
        - offset
      - State explicitly that these fields exist because receiver must buffer by (msg_id, offset).
      - State explicitly that msg_id MUST equal request_id per spec.
      - Do not invent additional required fields unless directly specified in documents.
    acceptance_criteria:
      - DATA packet layout includes msg_id and offset.
      - ACK-only packet layout includes no payload.

  - step: Define receiver validation behavior tied to packet format
    actions:
      - Specify: checksum fail => drop (receiver state table).
      - Specify: seq==expected => deliver segment + ACK; seq>expected => buffer + ACK; seq<expected => duplicate ACK.
      - Specify ACK number meaning: highest contiguous in-order seq received.
      - Specify rwnd included in every outgoing ACK.
    acceptance_criteria:
      - Behavior statements align with spec receiver table + ACK semantics section.

  - step: Define packing/unpacking contract (no code)
    actions:
      - Write a clear contract for:
        - how to parse fixed header
        - how to interpret presence/absence of reassembly fields based on flags (DATA vs ACK-only)
        - how to compute payload boundaries (remaining bytes after header)
      - Specify what constitutes a "valid packet" for purposes of "ACK every valid packet".
    acceptance_criteria:
      - Contract is deterministic and implementable.
      - No ambiguity on when msg_id/offset exist.

  - step: Document edge cases related to format (format-level only)
    actions:
      - Duplicate DATA packet (same seq): triggers duplicate ACK immediately.
      - Out-of-order DATA: buffered; ACK remains cumulative (does not jump).
      - rwnd=0 handling note: ACK still advertises rwnd=0 (sender waits elsewhere; format unchanged).
    acceptance_criteria:
      - Edge cases are phrased as format+semantics, not full algorithm.

definition_of_done:
  - The spec contains:
    - Header table with fixed sizes
    - DATA + ACK-only layout diagrams
    - Explicit references:
      - msg_id=request_id
      - buffer by (msg_id, offset)
      - ACK semantics
      - receiver state table behavior
    - A serialization contract that can be implemented consistently
  - No extra header fields beyond fixed-width header are introduced.