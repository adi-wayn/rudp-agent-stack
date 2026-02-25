---
description: Implement Dynamic RTO Calculation using the Jacobson/Karels algorithm and Karn's Algorithm in the RUDPSender.
---

---
description: Implement Dynamic RTO Calculation using the Jacobson/Karels algorithm and Karn's Algorithm in the RUDPSender.
---

# Workflow: day9_dynamic_rto

description: >
  Upgrade `common/rudp_sender.py` to calculate the Retransmission Timeout (RTO) dynamically 
  based on actual network latency (RTT). Implement the Jacobson/Karels equations and 
  enforce Karn's algorithm to ignore retransmitted packets during RTT sampling.

goal:
  Replace the static RTO timer with a highly responsive dynamic RTO that adapts to network 
  conditions, preventing premature timeouts on slow links and sluggish recovery on fast links.

inputs:
  - `common/rudp_sender.py`

constraints:
  - Use alpha = 0.125 and beta = 0.25 for the EWMA (Exponentially Weighted Moving Average).
  - Minimum RTO should be clamped (e.g., 0.1s or 100ms) to prevent it from dropping to zero.
  - Maximum RTO should be clamped (e.g., 60.0s).
  - Strictly implement Karn's Algorithm: Do NOT use ACKs from retransmitted packets to update SRTT/RTTVAR.

steps:

  - step: 1️⃣ State Initialization
    actions:
      - In `RUDPSender.__init__`, initialize:
        `self.srtt = None` (Smoothed RTT)
        `self.rttvar = None` (RTT Variance)
        `self.min_rto = 0.1` (seconds)
        `self.max_rto = 60.0` (seconds)
        Keep `self.rto = INITIAL_RTO` as the starting value.
    acceptance_criteria:
      - The required variables for Jacobson/Karels math are initialized.

  - step: 2️⃣ Track Retransmissions (Karn's Algorithm Prep)
    actions:
      - In `_try_send`, when adding a packet to `self.unacked_packets`, set a flag: `"is_retransmitted": False`.
      - In `check_timeouts` and the Fast Retransmit block of `on_ack_received`, when a packet is resent, update its entry: `"is_retransmitted": True`.
    acceptance_criteria:
      - The sender accurately knows if a specific sequence number has ever been retransmitted.

  - step: 3️⃣ Jacobson/Karels Math on ACK
    actions:
      - In `on_ack_received`, when a valid ACK clears packets from `self.unacked_packets`, find the highest sequence number that was just acknowledged.
      - If that packet has `"is_retransmitted" == False`:
        - Calculate `sample_rtt = current_time - sent_time`.
        - If `self.srtt` is None (first measurement):
          `self.srtt = sample_rtt`
          `self.rttvar = sample_rtt / 2`
        - Else:
          `self.rttvar = (1 - 0.25) * self.rttvar + 0.25 * abs(self.srtt - sample_rtt)`
          `self.srtt = (1 - 0.125) * self.srtt + 0.125 * sample_rtt`
        - Update RTO: `self.rto = self.srtt + 4 * self.rttvar`
        - Clamp RTO: `self.rto = max(self.min_rto, min(self.rto, self.max_rto))`
    acceptance_criteria:
      - RTO dynamically adjusts based only on cleanly transmitted packets.

  - step: 4️⃣ Exponential Backoff on Timeout (Karn's Phase 2)
    actions:
      - In `check_timeouts`, when an RTO expires, before retransmitting, double the RTO (Exponential Backoff): `self.rto = min(self.rto * 2, self.max_rto)`.
    acceptance_criteria:
      - Network congestion collapses are avoided by exponentially increasing the wait time during severe loss.