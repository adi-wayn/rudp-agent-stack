---
description: Generate the full Reliable UDP module implementation.
---

# Workflow: implement_reliable_udp
description: Generate the full Reliable UDP module implementation.

steps:
1. Read the specification doc for Reliable UDP.
2. Create packet header class struct with fields: seq, ack, flags, rwnd, checksum, payload.
3. Implement sender logic:
   - Sliding window
   - cwnd, ssthresh
   - RTO timer management
   - Fast retransmit on triple dupACK
4. Implement receiver logic:
   - Validate CRC/checksum
   - Buffer out-of-order (Selective Repeat)
   - Cumulative ACK semantics
   - Advertise rwnd
5. Integrate RUDP with the Transport interface.
6. Write unit tests for:
   - Loss scenarios
   - Out-of-order
   - Duplicate packets
   - rwnd throttling
7. Provide example usage snippet for client and server.