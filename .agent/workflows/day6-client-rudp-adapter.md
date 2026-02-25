---
description: Implement the Client-side Reliable UDP I/O Adapter using the OS-level UDP connect() pattern. Focus strictly on network framing, serialization integration, and isolated receive loops. No reliability algorithms yet.
---

---
description: Implement the Client-side Reliable UDP I/O Adapter using the OS-level UDP connect() pattern. Focus strictly on network framing, serialization integration, and isolated receive loops. No reliability algorithms yet.
---

# Workflow: day6_client_rudp_adapter

description: >
  Implement the `RUDPClientTransport` class in `client/transport/rudp_client.py`.
  This adapter acts as the Layer 4 I/O boundary. Unlike the server, the client is strictly
  point-to-point with a single server. You must utilize the UDP `connect()` pattern to 
  bind the socket at the OS level, enabling standard `send/recv` calls and implicitly 
  filtering rogue packets. Do NOT implement Day 7/8 reliability logic (sliding windows, 
  RTOs, ACKs) yet.

goal:
  Produce a robust network I/O adapter for the client that reads raw bytes from the wire, 
  validates checksums via the `RUDPPacket` class, drops corrupted packets, and forwards 
  valid packets to a stub handler for future processing.

inputs:
  - `common/rudp_packet.py` (Specifically `RUDPPacket.pack()` and `RUDPPacket.unpack()`)
  - System Specification (Transport Layer)

constraints:
  - STRICTLY NO reliability logic (Sliding Window, Retransmissions, Congestion Control).
  - Use built-in Python `socket` module (`AF_INET`, `SOCK_DGRAM`).
  - MUST catch and handle `ChecksumError` and `ValueError` by dropping the packet silently (simulating network loss).
  - MUST run the receive loop in a background thread or asynchronous task to avoid blocking the main client CLI.

steps:

  - step: 1️⃣ Socket Initialization & OS Binding
    actions:
      - Define `RUDPClientTransport(server_host, server_port)`.
      - Create a UDP socket.
      - Call `socket.connect((server_host, server_port))` on the UDP socket.
      - Document in a concise inline comment why `connect()` is used for UDP here (OS-level address association, enables `recv()` instead of `recvfrom()`, drops packets from unexpected IPs).
    acceptance_criteria:
      - Socket is properly configured and connected to the target server tuple.

  - step: 2️⃣ Implement Raw Send Boundary
    actions:
      - Implement `send_raw_packet(self, packet: RUDPPacket) -> None`.
      - Call `packet.pack()` to serialize the packet and compute the checksum.
      - Send the resulting bytes using `self.socket.send(bytes)`.
    acceptance_criteria:
      - Method correctly serializes and transmits the packet to the connected endpoint.

  - step: 3️⃣ Implement the Transport Receive Loop
    actions:
      - Implement a `_receive_loop(self)` method designed to run continuously.
      - Read data using `self.socket.recv(65535)`.
      - Attempt to deserialize the bytes using `RUDPPacket.unpack(data)`.
      - Wrap the unpack call in a `try...except` block targeting `ChecksumError` and `ValueError`.
      - On exception: Log a warning (e.g., "Corrupted packet received, dropping...") and `continue` the loop. DO NOT crash the client.
    acceptance_criteria:
      - Loop safely reads bytes and handles framing/checksum errors explicitly by simulating a packet drop.

  - step: 4️⃣ Implement State Machine Stub
    actions:
      - Implement `on_packet_received(self, packet: RUDPPacket) -> None`.
      - For Day 6, this is just a stub/placeholder. Simply log the received packet's sequence number and flags.
      - In the `_receive_loop`, pass successfully parsed packets to this method.
    acceptance_criteria:
      - Valid packets are successfully routed to the `on_packet_received` stub.
      - Ready for Day 8 logic injection.

  - step: 5️⃣ Lifecycle Management
    actions:
      - Implement `start(self)` to spin up the `_receive_loop` thread as a daemon.
      - Implement `close(self)` to signal the loop to terminate and close the socket safely.
    acceptance_criteria:
      - Clean startup and teardown of the background thread and network resources.

definition_of_done:
  - `client/transport/rudp_client.py` is fully implemented.
  - The OS-level UDP `connect()` paradigm is utilized correctly.
  - Integration with `RUDPPacket.unpack()` explicitly drops checksum failures.
  - The code contains NO Day 7/8 state machine logic (no sequence tracking, no ACKs, no timers).
  - Clean, professional Python code with appropriate type hinting and logging.