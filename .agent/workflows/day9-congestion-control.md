---
description: Implement the Congestion Control State Machine (Slow Start, Congestion Avoidance, Fast Recovery, and Timeout) in the RUDPSender.
---

---
description: Implement the Congestion Control State Machine (Slow Start, Congestion Avoidance, Fast Recovery, and Timeout) in the RUDPSender.
---

# Workflow: day9_congestion_control

description: >
  Upgrade `common/rudp_sender.py` from a fixed window size to a dynamic Congestion Window (`cwnd`).
  Implement the state machine defined in the Day 9 specification (Slow Start, Congestion Avoidance, 
  Fast Recovery, Timeout). The sender must now measure in-flight data in Bytes and dynamically 
  adjust `cwnd` based on network feedback (ACKs, DupACKs, and RTOs).

goal:
  Produce a network-aware RUDP Sender that properly scales its transmission rate and avoids 
  network collapse, adhering strictly to the provided state machine diagram.

inputs:
  - `common/rudp_sender.py`
  - `common/constants.py` (for MSS)

constraints:
  - `cwnd` must be tracked in Bytes (or multiples of MSS). Initial `cwnd` = 1 * MSS.
  - Initial `ssthresh` should be a high value (e.g., 65535 or defined in constants).
  - Do NOT implement Receiver Flow Control (`rwnd`) in this step, assume `rwnd` is infinite for now. Focus strictly on `cwnd`.

steps:

  - step: 1️⃣ State Initialization & Variables
    actions:
      - Define an Enum for Congestion States: `CC_SLOW_START`, `CC_AVOIDANCE`, `CC_FAST_RECOVERY`.
      - In `RUDPSender.__init__`, initialize: 
        `self.cc_state = CC_SLOW_START`
        `self.cwnd = MSS`
        `self.ssthresh = 65535` (or a large constant)
        `self.dup_ack_count = 0`
        `self.last_ack_received = 0`
    acceptance_criteria:
      - The Sender is initialized with the correct variables to track congestion state and duplicate ACKs.

  - step: 2️⃣ Enforce Congestion Window (In-flight Bytes)
    actions:
      - Modify `_try_send(current_time)` to respect `self.cwnd`.
      - Calculate `inflight_bytes` by summing the length of the payload of all packets currently in `self.unacked_packets`.
      - The sender can only pop from `send_buffer` and transmit if `inflight_bytes + next_packet_length <= self.cwnd`.
    acceptance_criteria:
      - The sender's transmission rate is strictly bounded by the dynamic `cwnd` instead of the old fixed `window_size`.

  - step: 3️⃣ Process New ACKs (Growth Mechanics)
    actions:
      - In `on_ack_received`, if `ack_num > self.base` (A NEW ACK):
        - Reset `self.dup_ack_count = 0`.
        - Update `self.last_ack_received = ack_num`.
        - If state is `CC_SLOW_START`: increase `cwnd += MSS`. If `cwnd >= ssthresh`, change state to `CC_AVOIDANCE`.
        - If state is `CC_AVOIDANCE`: increase `cwnd += (MSS * MSS) / cwnd` (equivalent to 1 MSS per RTT).
        - If state is `CC_FAST_RECOVERY`: change state to `CC_AVOIDANCE` (new ACK acknowledging loss) and optionally deflate `cwnd`.
    acceptance_criteria:
      - `cwnd` grows exponentially in Slow Start and linearly in Congestion Avoidance based on the MMD diagram.

  - step: 4️⃣ Process Duplicate ACKs (Fast Recovery)
    actions:
      - In `on_ack_received`, if `ack_num == self.last_ack_received` (A DUPLICATE ACK):
        - Increment `self.dup_ack_count`.
        - If `self.dup_ack_count == 3` (and not already in Fast Recovery):
          - Change state to `CC_FAST_RECOVERY`.
          - Set `ssthresh = max(self.cwnd / 2, 2 * MSS)`.
          - Set `cwnd = ssthresh + 3 * MSS`.
          - **FAST RETRANSMIT**: Immediately retransmit the oldest unacknowledged packet (`self.base`), bypassing the RTO timer!
        - If `self.dup_ack_count > 3` (already in Fast Recovery): `cwnd += MSS` (inflate window).
    acceptance_criteria:
      - Receiving 3 Duplicate ACKs triggers an immediate retransmission of the missing segment and reduces the window.

  - step: 5️⃣ RTO Timeout Handling
    actions:
      - In `check_timeouts`, if a timeout occurs (`current_time - sent_time >= RTO`):
        - Set `ssthresh = max(self.cwnd / 2, 2 * MSS)`.
        - Set `cwnd = 1 * MSS`.
        - Change state to `CC_SLOW_START` (the `CC_TIMEOUT` transition in the MMD diagram).
        - Proceed with retransmitting the oldest unacknowledged packet.
    acceptance_criteria:
      - A full RTO timeout drastically drops the window to 1 MSS and restarts Slow Start.

definition_of_done:
  - `RUDPSender` fully implements dynamic window sizing according to TCP Reno mechanics.
  - Comprehensive unit tests simulate ACKs and DupACKs to verify mathematically that `cwnd` grows and shrinks correctly across all states.