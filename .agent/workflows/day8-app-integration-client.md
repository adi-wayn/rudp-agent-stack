---
description: Integrate the Application Layer (AgentClient & Interactive CLI) with the newly completed RUDPClientTransport. Enable real-time transport toggling via the interactive menu, wire the request_id correctly, and connect the delivery callbacks.
---

---
description: Integrate the Application Layer (AgentClient & Interactive CLI) with the newly completed RUDPClientTransport. Enable real-time transport toggling via the interactive menu, wire the request_id correctly, and connect the delivery callbacks.
---

# Workflow: day8_app_integration_interactive_client

description: >
  Connect the Application Layer (`client/agent_client.py` and `client/cli/*`) to 
  the Layer 4 `RUDPClientTransport`. Since the CLI is an interactive menu-driven 
  application, we need to add a transport toggle to the UI, manage the transport 
  mode in the CLI State, and ensure the `AgentClient` correctly passes the `request_id` 
  during transmission.

goal:
  Achieve a fully functioning End-to-End Client application with an interactive UI 
  that can switch between TCP and RUDP transports seamlessly, allowing users to 
  execute tasks and uploads over Reliable UDP.

inputs:
  - `client/cli/state.py`
  - `client/cli/interactive_menu.py` (or the relevant network actions menu)
  - `client/transport/factory.py` (or transport initialization logic)
  - `client/agent_client.py`
  - `client/transport/tcp_client.py`

constraints:
  - Do NOT break existing TCP functionality. Both must work.
  - The UI must remain interactive and not block indefinitely.
  - Ensure the transport interface `send(data, request_id)` is satisfied.

steps:

  - step: 1️⃣ CLI State and Menu Integration
    actions:
      - Modify `client/cli/state.py` to hold the current `transport_mode` (defaulting to 'TCP').
      - Modify `client/cli/interactive_menu.py` (or `client/cli/actions/network.py`) to add a menu option: "Toggle Transport (Current: TCP/UDP)".
      - When toggled, the CLI should safely close the old transport and request the `AgentClient` (or factory) to initialize the new transport.
    acceptance_criteria:
      - The user can dynamically switch between TCP and Reliable UDP via the interactive UI.

  - step: 2️⃣ Transport Initialization & Lifecycle
    actions:
      - Update the transport instantiation logic (`factory.py` or inside `AgentClient`).
      - If UDP is selected, instantiate `RUDPClientTransport(host, port)`.
      - **CRITICAL:** Ensure `transport.start()` is called for RUDP to boot up the tick-generator loop. TCP might not need this, so handle polymorphically.
    acceptance_criteria:
      - The correct transport class is spun up and its background threads are started safely.

  - step: 3️⃣ Agent Client Interface Alignment
    actions:
      - In `client/agent_client.py`, locate where `transport.send()` is called.
      - Update it to pass the `request_id`: `self.transport.send(encoded_envelope, request_id)`.
      - **Crucial backward compatibility:** Ensure `TCPClientTransport.send()` is updated to accept `request_id` as an optional parameter (e.g., `def send(self, data: bytes, request_id: int = 0):`) so it doesn't crash when `AgentClient` passes it.
    acceptance_criteria:
      - `AgentClient` correctly feeds the `request_id` (used as `msg_id` for RUDP) into the Transport layer without breaking TCP.

  - step: 4️⃣ Response Callback Wiring
    actions:
      - In `client/agent_client.py`, ensure it registers its receive handler with the new transport: `self.transport.set_message_handler(self._on_message_received)`.
      - Ensure the async/event waiting logic in the CLI correctly waits for responses arriving via the RUDP background tick-loop.
    acceptance_criteria:
      - Reassembled Application payloads seamlessly flow from `RUDPReceiver` directly to the CLI output, resolving the user's pending action.

definition_of_done:
  - The interactive CLI displays the current transport mode.
  - The user can toggle between TCP and UDP from the menu.
  - Commands like `upload` or `task` successfully route through `RUDPSender` when UDP is active.