---
trigger: always_on
---

# Logging and Tracing Rules

* Log all state transitions in transport and application layers.
* For RUDP, log:
  - seq numbers sent/received
  - ACK numbers
  - cwnd, rwnd changes
  - timeouts/retransmissions
* For Agent, log:
  - request_id
  - selected execution plan
  - result metrics (duration, size)
* Logs must include timestamps and component tags.