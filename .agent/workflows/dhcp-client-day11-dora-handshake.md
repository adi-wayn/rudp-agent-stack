---
description: Implement the DHCP client DORA flow (Discover/Offer/Request/ACK) with timeout + retry logic.
---

# Workflow: dhcp_client_day11_dora_handshake
description: Implement the DHCP client DORA flow (Discover/Offer/Request/ACK) with timeout + retry logic.

goal:
Acquire a virtual IP lease by performing a standards-inspired DORA handshake and transitioning the client to the BOUND state.

steps:

1. Read DHCP specification in the System Specification:
   - DORA sequence: Discover (Broadcast), Offer (Unicast), Request (Broadcast), ACK (Unicast)
   - Packet fields: XID, client MAC, offered IP, lease time
   - Ports: UDP 68 (client) / 67 (server)

2. Define DHCP client state machine:
   - INIT → SELECTING → REQUESTING → BOUND
   - Store per-attempt xid, selected_ip, lease_time, lease_expiry

3. Implement packet encode/decode contract:
   - Message types: DISCOVER / OFFER / REQUEST / ACK
   - Required fields:
     - xid (32-bit)
     - client_mac
     - offered_ip / requested_ip (as applicable)
     - lease_time

4. Implement UDP socket setup:
   - Bind client socket to port 68
   - Enable broadcast for DISCOVER/REQUEST
   - Configure receive timeout dynamically (per backoff)

5. Send DISCOVER (Broadcast) + wait OFFER:
   - Generate new xid for the handshake attempt
   - Send DISCOVER with xid + client_mac
   - Wait for OFFER matching xid
   - Validate OFFER contains offered_ip + lease_time

6. Send REQUEST (Broadcast) + wait ACK:
   - Send REQUEST with xid + client_mac + requested_ip=offered_ip
   - Wait for ACK matching xid
   - Validate ACK confirms the requested/offered IP

7. Retry policy (mandatory):
   - Start timer after each send
   - On timeout: exponential backoff (timeout *= 2)
   - Max retries: 5
   - Abort and return failure after exceeding retries

8. Edge-case handling:
   - Ignore packets with non-matching xid
   - Ignore unexpected message type for current state
   - Handle duplicate offers/acks (idempotent receive)
   - If server indicates collision/NACK (if supported): restart DORA

9. Logging:
   - xid, state transitions, retries, timeout/backoff values
   - offered_ip/assigned_ip, lease_time, lease_expiry
   - timeouts and abort events

10. Verification:
   - Local run: reach BOUND and print assigned_ip + lease_expiry
   - Failure injection: simulate missing OFFER/ACK and confirm retries + abort at 5
   - Wireshark capture: show DISCOVER/OFFER/REQUEST/ACK (and retransmissions if any)

definition_of_done:
- DHCP client completes DORA and reaches BOUND with assigned_ip and lease metadata stored.
- Correct filtering by xid and expected message type per state.
- Retry logic works with exponential backoff and stops after 5 attempts.
- Logs clearly show handshake progress and failures.
- Smoke test and retry test scenarios pass.