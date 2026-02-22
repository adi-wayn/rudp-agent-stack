---
description: description: Implement the Reliable UDP Sender Logic (Layer 4) featuring sequence tracking, fixed sliding window, packet fragmentation (MSS), and tick-based RTO timeouts for retransmission.
---

---
description: Implement the Reliable UDP Sender Logic (Layer 4) featuring sequence tracking, fixed sliding window, packet fragmentation (MSS), and tick-based RTO timeouts for retransmission.
---

# Workflow: day7_rudp_sender

description: >
  Implement the `RUDPSender` class in `common/rudp_sender.py`.
  This component acts as the "brain" for outbound reliability. Since our architecture 
  is strictly single-threaded (no background threading/async for timers), the RTO 
  (Retransmission Timeout) MUST be implemented using a tick-based approach 
  (`check_timeouts(current_time)`). The sender must fragment large data payloads, 
  manage a sliding window buffer, handle Cumulative ACKs, and perform single-packet 
  retransmission upon timeout.

goal:
  Produce an architecture-compliant `RUDPSender` that manages the Reliable UDP Sender 
  State Machine (as per `Reliable UDP Sender.mmd`), without implementing Day 9's 
  Congestion Control (cwnd logic). Use a fixed static window size for now.

inputs:
  - `common/rudp_packet.py` (RUDPPacket framing)
  - `System Specification.pdf` (Section 8.16.3 / 8.16.5)

constraints:
  - NO THREADS OR ASYNCIO. Timeouts are checked via a manual `tick` polling method.
  - MSS (Maximum Segment Size) should be reasonably defined (e.g., 1024 bytes) to leave room for headers.
  - Initial RTO = 500ms (as per spec).
  - Use Cumulative ACKs: An ACK for `N` implies all packets with `seq < N` are acknowledged.
  - Retransmit ONLY the oldest unacknowledged segment upon timeout (not all of them).
  - Do NOT implement Congestion Control (cwnd, ssthresh) yet. That is reserved for Day 9.

steps:

  - step: 1️⃣ State Initialization
    actions:
      - Create `RUDPSender` class.
      - Initialize state variables: `base = 0`, `next_seq = 0`.
      - Initialize constants: `window_size = 10` (fixed for Day 7), `MSS = 1024`, `rto = 500` (ms).
      - Initialize buffers: `send_buffer` (list/deque of packets waiting to enter the window), `unacked_packets` (dict mapping `seq_num -> {"packet": RUDPPacket, "sent_time": float}`).
      - Add a callback reference `send_callback(bytes)` that the transport adapter will provide to physically send bytes.
    acceptance_criteria:
      - Class correctly encapsulates all sliding window variables and avoids thread-based timers.

  - step: 2️⃣ Fragmentation and Buffering (`enqueue_data`)
    actions:
      - Implement `enqueue_data(self, data: bytes, msg_id: int)`.
      - Calculate chunks based on `MSS`.
      - For each chunk, create an `RUDPPacket` with `seq_num = next_seq`, and `offset`.
      - Increment `next_seq`.
      - Append created packets to `send_buffer`.
      - Call `_try_send(current_time)`.
    acceptance_criteria:
      - Data is correctly fragmented and sequenced according to specification limits.

  - step: 3️⃣ The Sliding Window Execution (`_try_send`)
    actions:
      - Implement `_try_send(self, current_time: float)`.
      - Loop while `len(unacked_packets) < window_size` AND `send_buffer` is not empty.
      - Pop packet from `send_buffer`.
      - Add it to `unacked_packets` storing the `current_time`.
      - Call `send_callback(packet.pack())`.
    acceptance_criteria:
      - Packets are only sent if the inflight count is strictly less than the window size (Pipelining).

  - step: 4️⃣ Cumulative ACK Processing
    actions:
      - Implement `on_ack_received(self, ack_num: int, current_time: float)`.
      - If `ack_num > base`: Update `base = ack_num`.
      - Remove all packets from `unacked_packets` where `seq_num < ack_num` (Cumulative).
      - Call `_try_send(current_time)` to push new packets into the newly opened window space.
    acceptance_criteria:
      - Window slides forward upon receiving a valid, higher ACK. Old packets are cleared.

  - step: 5️⃣ Tick-Based Retransmission Timer
    actions:
      - Implement `check_timeouts(self, current_time: float)`.
      - If `unacked_packets` is empty, do nothing.
      - Find the oldest unacknowledged packet (which is always at `seq_num == base`).
      - If `current_time - unacked_packets[base]['sent_time'] >= self.rto`:
          - Update the `'sent_time'` for this packet to `current_time` (resetting the timer).
          - Retransmit this single packet via `send_callback(packet.pack())`.
          - Log a retransmission event.
    acceptance_criteria:
      - Single-packet retransmission on timeout is flawlessly executed without threads, strictly using time deltas.

definition_of_done:
  - `common/rudp_sender.py` is fully implemented.
  - The implementation passes purely as a state machine manipulated by external time ticks.
  - Cumulative ACKs properly advance the `base` and clear memory.
  - Obeys the "Retransmit oldest unacknowledged segment" rule from section 8.16.3.