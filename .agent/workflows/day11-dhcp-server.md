---
description: Implement the Custom DHCP Server based on the System Specification (Day 11).
---

---
description: Implement the Custom DHCP Server based on the System Specification (Day 11).
---

# Workflow: day11_dhcp_server

description: >
  Implement the server-side of the virtual DHCP protocol. The server must handle DORA 
  (Discover, Offer, Request, ACK/NACK) handshakes, manage a virtual IP pool in the 
  127.x.x.x range (excluding 127.0.0.1), and maintain a `leased_ips` state machine.

goal:
  Produce a fully functional standalone UDP DHCP Server that correctly parses incoming 
  client requests, assigns virtual IPs, handles edge cases (IP collisions, duplicate XIDs), 
  and logs operations according to the spec.

inputs:
  - `System Specification.pdf` (Section 2, Section 8.9)
  - `common/constants.py`

constraints:
  - Must use raw UDP sockets (NO RUDP or TCP here).
  - Server listens on port 67, sends to port 68.
  - Required Packet Fields: XID (32-bit), Client MAC, Offered IP, Lease Time.
  - Maintain `leased_ips` tracking SELECTING and BOUND states.

steps:

  - step: 1️⃣ Create DHCP Packet Definition
    actions:
      - Create `common/dhcp_packet.py`.
      - Define a class `DHCPPacket` with fields: `message_type` (DISCOVER, OFFER, REQUEST, ACK, NACK), `xid`, `client_mac`, `offered_ip`, `lease_time`.
      - Implement `to_bytes()` and `from_bytes()` (using structured JSON or struct packing).
    acceptance_criteria:
      - DHCP messages can be safely serialized and deserialized over UDP.

  - step: 2️⃣ Create IP Pool & Lease Manager
    actions:
      - Create `server/dhcp/ip_manager.py` with an `IPManager` class.
      - Initialize a pool of available IPs (e.g., `127.0.0.2` to `127.0.0.254`).
      - Maintain a dictionary `self.leased_ips` mapping `client_mac` to `{"ip": ..., "xid": ..., "expires_at": ..., "state": "SELECTING" | "BOUND"}`.
      - Implement methods: `handle_discover(mac, xid)`, `handle_request(mac, xid, requested_ip)`, and `cleanup_expired_leases()`.
      - Ensure Edge Case handling: If IP collision occurs during `handle_request`, return None/Error to trigger a NACK.
    acceptance_criteria:
      - IPs are correctly leased, states transition correctly, and duplicates/collisions are handled deterministically.

  - step: 3️⃣ Implement the DHCP Server
    actions:
      - Create `server/dhcp_server.py`.
      - Bind a UDP socket to `127.0.0.1` port `DHCP_SERVER_PORT` (67).
      - Run a continuous `recvfrom` loop.
      - On DISCOVER: Query `IPManager`, generate an OFFER, and `sendto` the client's source address on port `DHCP_CLIENT_PORT` (68).
      - On REQUEST: Query `IPManager`. If successful, send ACK. If IP collision, send NACK.
      - Log precisely as per spec: `logger.info(f"DHCP: XID={xid}, Allocated IP={ip}, Lease Expiry={expiry}")`.
    acceptance_criteria:
      - Server responds correctly to client broadcasts/unicasts and outputs the mandated logs.

definition_of_done:
  - Server runs successfully and binds to port 67.
  - IP Manager handles DORA logic without networking concerns.
  - Edge cases (Duplicate XIDs, Collisions) are mitigated per the specification.