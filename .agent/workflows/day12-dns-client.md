---
description: Implement the DoH Client over custom RUDP for the Interactive CLI (Day 12).
---

---
description: Implement the DoH Client over custom RUDP for the Interactive CLI (Day 12).
---

# Workflow: day12_dns_client

description: >
  Implement the client-side DNS resolution. The client must explicitly use the custom 
  Layer 4 Reliable UDP (RUDP) transport to send an HTTP GET request to the DoH server. 
  It must parse the raw HTTP JSON response and update the CLI state.

goal:
  Produce a `DNSClient` that resolves domain names (e.g., 'agent.local') by communicating 
  with the `DoHRUDPServer` on 127.0.0.1:8053 over RUDP. Integrate this into Option 2 of the CLI.

inputs:
  - Existing `RUDPClientTransport`.
  - The acquired `client_ip` from the Session State (to ensure binding constraints).

constraints:
  - DO NOT use Python's `requests` or `urllib`. All HTTP formatting/parsing must be manual over RUDP.
  - The client must bind to the DHCP-assigned `client_ip` (Virtual IP) before sending the query.
  - Must handle HTTP timeouts or 404 Not Found gracefully.

steps:

  - step: 1️⃣ Create the DNS DoH Client
    actions:
      - Create `client/dns_client.py`.
      - Define `class DNSClient`. The constructor should accept `client_ip` (default "NOT_SET").
      - Implement method `resolve(domain_name: str) -> str | None`.
      - Inside `resolve`:
        1. Instantiate `RUDPClientTransport(server_host="127.0.0.1", server_port=8053, client_ip=self.client_ip)`.
        2. Call `transport.connect()`.
        3. Format an HTTP GET request string: `GET /dns-query?name={domain_name} HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n`.
        4. Send the encoded string via `transport.send(...)`.
        5. Await response via `transport.receive(...)`.
        6. Parse the response: split the HTTP headers from the body using `\r\n\r\n`.
        7. Load the JSON body. If status is 200, return the extracted `ip`. Else return `None`.
        8. Close the transport.
    acceptance_criteria:
      - Can successfully construct an HTTP GET, extract the JSON body from an HTTP response, and return the mapped IP.

  - step: 2️⃣ Integrate into the CLI Network Actions
    actions:
      - Modify `client/cli/actions/network.py`.
      - Update the `action_dns(state)` hook.
      - Prompt the user: `Enter App Server hostname [agent.local]: `. Default to `agent.local`.
      - Instantiate `DNSClient(client_ip=state.client_ip)` and call `.resolve(hostname)`.
      - If successful, update `state.server_ip = resolved_ip`.
      - Print a success message: `✅ Resolved {hostname} to {resolved_ip}`.
      - Handle exceptions (e.g., timeout, connection refused) gracefully without crashing the UI.
    acceptance_criteria:
      - The UI properly routes Option 2 to the new `DNSClient` and updates the Header display from `Server IP: NOT_SET` to `Server IP: 127.0.0.1`.