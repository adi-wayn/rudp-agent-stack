---
description: Integrate the RUDPSender and RUDPReceiver into the Server multiplexing adapter (RUDPServerTransport). Implement a virtual connection manager to route packets per (IP, Port) tuple and broadcast ticks to all active senders.
---

---
description: Integrate the RUDPSender and RUDPReceiver into the Server multiplexing adapter (RUDPServerTransport). Implement a virtual connection manager to route packets per (IP, Port) tuple and broadcast ticks to all active senders.
---

# Workflow: day8_server_integration

description: >
  Perform the final Day 8 integration in `server/transport/rudp_server.py`.
  The server must multiplex incoming UDP packets from a single socket into isolated 
  "Virtual Connections", each containing its own `RUDPSender` and `RUDPReceiver`.
  The receive loop must operate with a timeout to act as a tick-generator, iterating 
  over all active connections to process timeouts.

goal:
  Produce a fully integrated Server Transport Layer that reliably handles multiple 
  simultaneous clients, managing individual sliding windows, out-of-order buffers, 
  and tick-based retransmissions.

inputs:
  - `server/transport/rudp_server.py`
  - `common/rudp_sender.py`
  - `common/rudp_receiver.py`
  - `common/rudp_packet.py`

constraints:
  - DO NOT implement Day 9 Congestion Control or flow control.
  - The socket MUST use `settimeout` (e.g., `0.05` seconds) to prevent blocking, allowing the tick engine to run.
  - Do NOT create a new thread per client. All multiplexing and ticks must happen in the single background `_receive_loop`.
  - Maintain the existing Application Interface signature if possible, but ensure `send` requires a `client_addr` tuple.

steps:

  - step: 1️⃣ Define the Virtual Connection Container
    actions:
      - Create an internal helper class `RUDPConnection`.
      - It should initialize its own `RUDPSender` and `RUDPReceiver`.
      - It needs references to the transport's `send_raw_packet` (bound to this specific client's address) and the application delivery callback.
    acceptance_criteria:
      - `RUDPConnection` correctly encapsulates the state for a single `(IP, Port)` peer.

  - step: 2️⃣ Multiplexing & Tick Engine Loop
    actions:
      - In `RUDPServerTransport`, define `self.connections = {}` mapping `client_addr -> RUDPConnection`.
      - Set `self.socket.settimeout(SOCKET_POLL_TIMEOUT)` (e.g., 0.05s).
      - In `_receive_loop()`, catch `socket.timeout` safely.
      - On receiving a valid packet, look up `addr` in `self.connections`. If it doesn't exist, create a new `RUDPConnection` and store it.
      - At the *end* of every loop iteration (whether data was received or timeout occurred), iterate over `self.connections.values()` and call `connection.sender.check_timeouts(current_time)`.
    acceptance_criteria:
      - The server smoothly handles missing packets via timeouts without starving any specific client.

  - step: 3️⃣ Route Incoming Packets
    actions:
      - Pass the parsed `RUDPPacket` to the corresponding `RUDPConnection`.
      - If `packet.is_ack()`: call `sender.on_ack_received()`.
      - If `packet.has_data()`: call `receiver.process_segment()`. Construct an ACK `RUDPPacket` with the returned `ack_num` and `rwnd`, and send it back immediately via `send_raw_packet`.
    acceptance_criteria:
      - ACKs and DATA are properly demultiplexed per client and per component.

  - step: 4️⃣ Expose Application Interface
    actions:
      - Implement `send(self, data: bytes, request_id: int, client_addr: tuple)`.
      - Ensure the method looks up the correct `RUDPConnection` and calls `enqueue_data` on its sender.
      - Implement `set_message_handler(self, callback)` so the Agent Server Pipeline can receive `(data, client_addr)`.
    acceptance_criteria:
      - The Application Layer can respond to specific clients using the transport's reliable abstraction.

definition_of_done:
  - `server/transport/rudp_server.py` is fully integrated with connection multiplexing.
  - The receive loop acts as a global tick-generator for all active sessions.
  - The server properly instantiates isolated senders/receivers per client address.