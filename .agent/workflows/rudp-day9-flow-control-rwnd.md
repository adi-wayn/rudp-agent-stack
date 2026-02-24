---
description: Implement RUDP Flow Control (Receive Window) and enforce effective sender window.
---

# Workflow: rudp_day9_flow_control_rwnd
description: Implement RUDP Flow Control (Receive Window) and enforce effective sender window.

goal:
Add receiver-side advertised window (rwnd) and enforce sender effective_window = min(cwnd, rwnd).

steps:

1. Review Specification:
   - Read RUDP Flow Control section (rwnd semantics).
   - Confirm MAX_RWND, HIGH_WATERMARK (80%), LOW_WATERMARK (20%).
   - Verify header field: 16-bit Window Size.

2. Receiver: Buffer Accounting
   - Track current buffer occupancy (in segments).
   - Define buffer_capacity = MAX_RWND.
   - Maintain state: FC_NORMAL / FC_THROTTLE.

3. Receiver: rwnd Calculation
   - rwnd = buffer_capacity - buffer_used.
   - If buffer_used >= 80% → enter FC_THROTTLE.
   - If buffer_used <= 20% → return to FC_NORMAL.
   - Ensure rwnd never negative.
   - Always advertise rwnd in outgoing ACK packets.

4. Sender: Enforce Effective Window
   - On every ACK received:
       - Extract advertised rwnd.
       - Store latest peer_rwnd.
   - Compute:
       effective_window = min(cwnd, peer_rwnd)
   - Allow sending only if:
       next_seq < base + effective_window

5. Zero Window Handling
   - If peer_rwnd == 0:
       - Enter S_WAIT_WINDOW state.
       - Pause data transmission.
       - Optionally implement Zero Window Probe logic.

6. Logging (Transport Layer)
   - Log for every ACK:
       - seq
       - ack
       - cwnd
       - rwnd
       - effective_window
   - Log state transitions:
       - FC_NORMAL → FC_THROTTLE
       - THROTTLE → NORMAL
       - Sender → S_WAIT_WINDOW

7. Edge Case Handling
   - Prevent buffer overflow.
   - Handle duplicate packets without increasing buffer usage.
   - Handle out-of-order segments correctly.
   - Ensure rwnd grows when data delivered to application.

8. Tests:
   - Normal transfer with sufficient buffer.
   - Simulated buffer saturation (force rwnd shrink).
   - rwnd = 0 scenario.
   - Recovery after buffer drains.
   - Validate behavior under packet loss + congestion control.

definition_of_done:
- Receiver dynamically advertises rwnd.
- Sender enforces effective_window = min(cwnd, rwnd).
- No buffer overflow occurs.
- rwnd shrinks at 80% usage and expands at 20%.
- rwnd=0 correctly pauses sender.
- Logs show cwnd/rwnd/effective_window transitions.
- Behavior validated with failure injection.