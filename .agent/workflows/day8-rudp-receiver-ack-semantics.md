---
description: Implement and validate RUDP receiver reliability semantics: out-of-order buffering, cumulative ACK, and duplicate ACK behavior (per spec), without touching application logic.
---

Workflow: day8_rudp_receiver_ack_semantics

description: Implement and validate RUDP receiver reliability semantics: out-of-order buffering, cumulative ACK, and duplicate ACK behavior (per spec), without touching application logic.

goal:
Ensure the RUDP receiver (per peer) correctly handles:

Out-of-order segment buffering (Selective Repeat-style receive window)

Cumulative ACK semantics (ACK = highest contiguous in-order seq received)

Duplicate ACK generation (for duplicates and for gaps)
This must work under loss/reordering/jitter and must not break the transport-agnostic application layer.

constraints:

DO NOT change application-layer logic (Agent pipeline, opcodes handling, tools).

DO NOT change main/CLI entrypoints.

Changes should be isolated to RUDP receiver logic (and minimal sender-side handling only if needed to consume dupACKs).

Follow spec semantics for ACK/rwnd and receiver behavior. 

System_Specification

steps:

Reconfirm Receiver Contract (Per Peer):

Input: incoming UDP datagrams parsed into RUDP segments (seq, ack, flags, rwnd, payload, checksum).

Output events:

deliver_payload(payload_bytes) ONLY when in-order contiguous

outgoing_ack(ack_num, rwnd, flags) for EVERY valid segment received

Invariant: receiver never “delivers” out-of-order payload to the application.

Define Receiver State (Per ConnectionPeer):

expected_seq: next sequence number required for in-order delivery (a.k.a. rcv_nxt)

ooo_buffer: map seq -> segment_payload (or full segment) for seq > expected_seq

recv_window_limit: maximum number of buffered segments (derived from MAX_RWND / buffer capacity)

rwnd_advertised: how much free buffer remains (segments count), sent on every ACK

(optional) stats: dup_count, ooo_count, drops_count for logging/tests

Implement Out-of-Order Buffering Rules:

On segment with seq > expected_seq:

If within receive window AND buffer has capacity:

store in ooo_buffer (do not deliver)

Else:

drop segment (still send ACK for current cumulative ack)

On segment with seq == expected_seq:

deliver immediately

increment expected_seq

then “drain”:

while expected_seq exists in ooo_buffer:

pop it, deliver it, expected_seq++

On segment with seq < expected_seq:

treat as duplicate (already received/delivered); do not deliver

Implement Cumulative ACK Semantics:

ACK number MUST represent:

“highest contiguous in-order seq received”

Practical rule:

ack_to_send = expected_seq - 1 (if seq starts at 0 or 1, adjust accordingly)

Send ACK on EVERY valid received segment (even out-of-order, even duplicates). 

System_Specification

Implement Duplicate ACK Behavior (Two Causes):
A) True duplicate segment:

if seq < expected_seq → immediately send ACK(ack_to_send) (duplicate ACK)
B) Gap detected (out-of-order arrival):

if seq > expected_seq → immediately send ACK(ack_to_send)

this generates repeated ACKs for the same ack number when more out-of-order segments arrive

This “dupACK stream” is what the sender can use for Fast Retransmit (3 dupACKs). 

System_Specification

Interplay With Flow Control (rwnd advertisement):

Compute rwnd_advertised from available buffer space (in segments).

Include rwnd in EVERY ACK.

If buffer usage is high (near HIGH_WATERMARK), shrink rwnd aggressively.

If buffer usage low (below LOW_WATERMARK), grow rwnd back toward MAX_RWND. 

System_Specification

Ensure sender’s effective window is min(cwnd, rwnd).

Safety & Edge Cases:

Checksum fail → drop segment, do not update state; (optionally still ACK last cumulative to help sender converge, but keep consistent)

Duplicate out-of-order storage:

if seq already in ooo_buffer, ignore (do not double count capacity)

Window boundary:

define “within window” precisely (expected_seq < seq <= expected_seq + window_span)

Buffer overflow:

drop newest out-of-window/over-capacity segments; keep sending cumulative ACK

Logging (Debug-Level, Receiver-Focused):

For each segment:

received seq, expected_seq, action taken: DELIVER / BUFFER / DUP / DROP

ack_sent and rwnd_sent

When draining buffer:

log drained seq range (e.g., “drain 41..47”)

Tests (Must Prove the Three Semantics):

Out-of-order delivery test:

send seq: 1,3,2,4 → verify application receives: 1,2,3,4

verify ACK stream: after seq3 arrives while expected=2, ACK stays at 1 until seq2 arrives

Cumulative ACK test:

deliver 1,2,3 → ACK should advance 1→2→3 (depending on base)

Duplicate segment test:

send seq2 twice after delivered → receiver must NOT deliver twice, must send duplicate ACK

Gap/dupACK stream test:

send 1,4,5,6 (missing 2,3) → receiver emits repeated ACK for 1 (dupACK behavior)

Stress test with jitter/reordering + loss injection:

confirm no out-of-order delivery, no state corruption across peers

Wireshark Validation Checklist:

Observe repeated ACK numbers when gaps exist (dupACKs)

Observe ACK number only advances when missing seq arrives (cumulative behavior)

Observe receiver does not emit “deliveries” out of order (validated via application-level logs correlated with seq)

definition_of_done:

Receiver buffers out-of-order segments and delivers to application strictly in-order.

ACK number is cumulative: always indicates highest contiguous in-order seq.

Duplicate ACKs are generated for duplicates and for out-of-order/gap situations.

rwnd is advertised on every ACK and reflects buffer capacity.

Verified with deterministic tests + a loss/reorder simulation run + Wireshark evidence.