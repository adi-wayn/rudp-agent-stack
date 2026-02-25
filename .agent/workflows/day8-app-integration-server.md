---
description: Integrate the Application Layer (AgentServer & CLI) with the completed RUDPServerTransport. Enable UDP selection via CLI flags, wire the request_id and client_addr correctly, and ensure TCP backward compatibility.
---

---
description: Integrate the Application Layer (AgentServer & CLI) with the completed RUDPServerTransport. Enable UDP selection via CLI flags, wire the request_id and client_addr correctly, and ensure TCP backward compatibility.
---

# Workflow: day8_app_integration_server

description: >
  Connect the Application Layer (`server/agent_server.py` and `server/__main__.py`) to 
  the Layer 4 `RUDPServerTransport`. This requires exposing a CLI flag (`--udp`) to boot 
  the server in RUDP mode, instantiating the correct transport, and ensuring the `AgentServer` 
  correctly passes both the `request_id` and the `client_addr` back to the transport 
  when sending responses.

goal:
  Achieve a fully functioning End-to-End Server application that can be booted in either 
  TCP or RUDP mode, correctly handling multiplexed client requests and responding with 
  the proper transport semantics.

inputs:
  - `server/__main__.py`
  - `server/agent_server.py`
  - `server/transport/tcp_server.py` (to align interfaces)
  - `server/transport/rudp_server.py`

constraints:
  - Do NOT break existing TCP functionality. 
  - Ensure the transport interface `send(data, request_id, client_addr)` is satisfied polmorphically.
  - The server should probably use `argparse` to accept a `--udp` flag upon startup.

steps:

  - step: 1️⃣ CLI Configuration for UDP (Server)
    actions:
      - Modify `server/__main__.py`.
      - Add a `--udp` boolean flag using `argparse` (or your existing CLI parser).
      - Based on the flag, instantiate either `TCPServerTransport` or `RUDPServerTransport`.
    acceptance_criteria:
      - The server administrator can explicitly choose Reliable UDP when starting the server.

  - step: 2️⃣ Transport Interface Alignment (TCP Safety)
    actions:
      - Modify `server/transport/tcp_server.py`.
      - Update its send signature to match RUDP: `def send(self, data: bytes, request_id: int = 0, client_addr: tuple = None)`.
      - Ensure it safely ignores `request_id` but uses `client_addr` to route the TCP response to the correct client socket (which it should already be doing, just ensure the signature matches).
    acceptance_criteria:
      - Both TCP and UDP transports share the exact same method signature so `AgentServer` does not need `if/else` logic.

  - step: 3️⃣ Agent Server Interface Alignment
    actions:
      - In `server/agent_server.py`, locate where responses are built and sent back to the client (likely near the end of the pipeline state machine).
      - When `transport.send()` is called, ensure it extracts the `request_id` from the incoming `AppEnvelope` and passes it: `self.transport.send(response_bytes, request_id, client_addr)`.
    acceptance_criteria:
      - The `AgentServer` correctly maps the request's ID to the response and pushes it down to Layer 4 with the exact client destination.

  - step: 4️⃣ Lifecycle Management
    actions:
      - Ensure `transport.start()` is called in `server/__main__.py` or `agent_server.start()`.
      - Ensure graceful shutdown of the transport on `KeyboardInterrupt` (closing the RUDP receive loop and sockets).
    acceptance_criteria:
      - Server boots, binds to the port, and handles ticks/requests indefinitely until killed.

definition_of_done:
  - The server can be launched with `python -m server --udp`.
  - The `AgentServer` logic remains transport-agnostic.
  - Test suites verify both TCP and RUDP modes instantiate correctly.