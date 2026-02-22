---
description: Integrate the RUDPSender and RUDPReceiver into the RUDPClientTransport adapter. Wire up the callbacks, manage the non-blocking receive loop for tick generation, and expose the application-facing send/receive interface.
---

---
description: Integrate the RUDPSender and RUDPReceiver into the RUDPClientTransport adapter. Wire up the callbacks, manage the non-blocking receive loop for tick generation, and expose the application-facing send/receive interface.
---

# Workflow: day8_client_integration

description: >
  Perform the final Day 8 integration in `client/transport/rudp_client.py`.
  We must integrate `RUDPSender` (Day 7) and `RUDPReceiver` (Day 8) into the I/O adapter (Day 6).
  The application layer must be able to use `transport.send(data, msg_id)` and receive fully 
  reassembled payloads seamlessly. No Day 9 logic (congestion control) should be added.

goal:
  Produce a fully integrated Client Transport Layer that handles windowed sending, out-of-order 
  receiving, ACKs, and tick-based retransmissions using a semi-blocking socket loop.

inputs:
  - `client/transport/rudp_client.py`
  - `common/rudp_sender.py`
  - `common/rudp_receiver.py`
  - `common/rudp_packet.py` (for FLAG_ACK and properties)

constraints:
  - DO NOT implement Day 9 Congestion Control or flow control (keep rwnd static or use default).
  - The socket `recv` loop must not block indefinitely, otherwise `sender.check_timeouts()` will starve. Use `socket.settimeout()` to generate frequent ticks.
  - The Application Layer interface (e.g., `send(data, request_id)` and setting an `on_message` callback) must be maintained.

steps:

  - step: 1️⃣ Socket Timeout & Tick Loop Refactor
    actions:
      - Modify `RUDPClientTransport.start()` or init to call `self.socket.settimeout(0.05)` (50ms).
      - In `_receive_loop()`, wrap `socket.recv()` in a try-except catching `socket.timeout` (or `BlockingIOError`).
      - On timeout, do nothing but `continue` the loop.
      - At the *end* of every loop iteration (whether a packet was received or it timed out), calculate `current_time = time.time()` and call `self.sender.check_timeouts(current_time)`.
    acceptance_criteria:
      - The receive loop acts as a tick-generator for the sender without freezing on `recv()`.

  - step: 2️⃣ Instantiate Sender & Receiver with Callbacks
    actions:
      - In `__init__`, instantiate `self.sender = RUDPSender(...)`.
        - The `send_callback` must point to `self.send_raw_packet` (from Day 6).
      - In `__init__`, instantiate `self.receiver = RUDPReceiver(...)`.
        - The `ack_callback(ack_num, rwnd)` must build an ACK-only `RUDPPacket` (no payload, no msg_id, flags=FLAG_ACK) and call `self.send_raw_packet(packet)`.
        - The `app_delivery_callback(data, msg_id)` should forward the reassembled data to the application layer via an `on_message_received` event/callback (store a reference to this in the transport).
    acceptance_criteria:
      - Components are correctly wired to network I/O and application callbacks.

  - step: 3️⃣ Route Incoming Packets
    actions:
      - In `_receive_loop()`, after successful `RUDPPacket.unpack()` (and checksum validation from Day 6):
      - If `packet.is_ack()` is True: call `self.sender.on_ack_received(packet.ack_num, current_time)`.
      - If `packet.has_data()` is True: call `self.receiver.on_packet_received(packet, current_time)`.
    acceptance_criteria:
      - Traffic is correctly demultiplexed between the Sender (ACKs) and Receiver (Data).

  - step: 4️⃣ Expose Application Interface
    actions:
      - Implement `send(self, data: bytes, request_id: int)`.
      - This method simply calls `self.sender.enqueue_data(data, request_id, time.time())`.
      - Ensure there is a way for the application to register a callback, e.g., `set_message_handler(self, callback)`.
    acceptance_criteria:
      - The Agent Application can push bytes into the transport layer completely unaware of RUDP internals.

definition_of_done:
  - `client/transport/rudp_client.py` is fully integrated.
  - Test suite verifies that a payload sent via `transport.send()` is chunked by the sender and passed to the raw socket.
  - The client runs without blocking indefinitely and actively ticks the RTO timer.