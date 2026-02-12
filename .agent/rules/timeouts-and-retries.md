---
trigger: always_on
---

# Timeouts and Retries Rules

* Client must implement exponential backoff:
  - Start timeout = 500ms
  - Max retries = 5
* Retransmit oldest unacknowledged packet on timeout.
* For 3 duplicate ACKs, use fast retransmit.
* RTO recalculation MUST use RFC-style RTT/DevRTT formulas.
* Avoid tight loops; include minimal sleeps/backoffs in retry loops.