---
description: Implement Network Failure Simulation (Day 10) to inject Packet Loss, Latency, and Duplicates using a Separation of Concerns (SOC) architecture.
---

---
description: Implement Network Failure Simulation (Day 10) to inject Packet Loss, Latency, and Duplicates using a Separation of Concerns (SOC) architecture.
---

# Workflow: day10_failure_simulation

description: >
  Implement a robust, non-intrusive Failure Engine to simulate real-world network conditions 
  (Drops, Latency, Duplicates). The engine must be configurable via CLI arguments and hook 
  into the RUDP transport layers in a way that allows Wireshark to capture the anomalies.

goal:
  Produce a network simulation layer that proves the resilience of the RUDP Congestion Control 
  and RTO mechanisms, with all failures visible in Wireshark PCAP recordings.

inputs:
  - `simulations/failure_engine.py`
  - `client/__main__.py`
  - `server/__main__.py`
  - `client/transport/rudp_client.py`
  - `server/transport/rudp_server.py`

constraints:
  - DO NOT pollute the Interactive CLI menu. Use `argparse` flags for startup injection.
  - **Wireshark Visibility:** Drops must happen INBOUND (after `recvfrom` but before processing). Latency and Duplicates must happen OUTBOUND (delaying or repeating `sendto`).
  - Strict SOC: Transport layers should not contain random/probability math. They only call the `FailureEngine` hooks.

steps:

  - step: 1️⃣ Implement the Failure Engine
    actions:
      - In `simulations/failure_engine.py`, create the `FailureEngine` class.
      - Initialize with `drop_rate` (0.0 to 1.0), `latency_ms` (tuple or int), and `dup_rate` (0.0 to 1.0).
      - Implement `should_drop_inbound() -> bool`: Returns True based on `drop_rate` probability.
      - Implement `apply_outbound(data: bytes, addr: tuple, send_func: callable)`:
        - If duplicate probability hits, call `send_func(data, addr)` immediately.
        - If latency applies, spawn a short-lived `threading.Timer` to call `send_func(data, addr)` after `latency_ms`.
        - Otherwise, call `send_func(data, addr)` normally.
    acceptance_criteria:
      - The FailureEngine encapsulates all probability and delay logic independently.

  - step: 2️⃣ CLI Configuration Injection
    actions:
      - In both `client/__main__.py` and `server/__main__.py`, add `argparse` arguments: `--loss` (int percentage), `--latency` (int ms), `--dup` (int percentage).
      - If any flag is > 0, instantiate the `FailureEngine` with the normalized values (e.g., 20% -> 0.2).
      - Pass the instantiated `FailureEngine` (or None if no flags) into the `RUDPClientTransport` and `RUDPServerTransport` constructors.
    acceptance_criteria:
      - The simulation can be activated externally without changing application code, maintaining clean production defaults.

  - step: 3️⃣ Inbound Interception (Packet Drops)
    actions:
      - In the `_receive_loop` of both `rudp_client.py` and `rudp_server.py`.
      - Immediately after `data, addr = self.sock.recvfrom(65535)`:
      - Add a check: `if self.failure_engine and self.failure_engine.should_drop_inbound(): continue` (or `return` if not in a loop).
      - Optional: Log a debug message indicating a packet was intentionally dropped by the engine.
    acceptance_criteria:
      - Packets arrive at the socket (visible to Wireshark) but are silently discarded by the app, triggering Sender Timeouts.

  - step: 4️⃣ Outbound Interception (Latency & Duplicates)
    actions:
      - In `rudp_client.py` and `rudp_server.py`, locate where `self.sock.sendto(data, addr)` is explicitly called (usually `send_raw_packet` or similar).
      - Replace it with:
        `if self.failure_engine: self.failure_engine.apply_outbound(data, addr, self.sock.sendto)`
        `else: self.sock.sendto(data, addr)`
    acceptance_criteria:
      - Wireshark captures delayed outbound packets or double outbound packets directly on the wire.

definition_of_done:
  - Both Client and Server can be launched with `--loss`, `--latency`, and `--dup` flags.
  - The Core RUDP logic remains oblivious to the simulations.
  - Wireshark recordings accurately reflect the applied anomalies.