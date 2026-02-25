---
description: Implement DNS over HTTP (DoH) using the Custom RUDP Transport (Day 12).
---

---
description: Implement DNS over HTTP (DoH) using the Custom RUDP Transport (Day 12).
---

# Workflow: day12_dns_server_doh_rudp

description: >
  Implement a local DNS Server that exclusively supports DNS over HTTP (DoH). 
  CRITICALLY: This DoH server MUST run over the custom Reliable UDP (RUDP) transport 
  layer, NOT standard TCP. It will parse raw HTTP GET requests from the RUDP payload.

goal:
  Produce a DoH Server that runs on RUDP port 8053. It manages a `DNSCache`, parses 
  HTTP queries, and returns HTTP-formatted JSON responses. Integrate this into the Orchestrator.

inputs:
  - `System Specification.pdf` (Section 2 - Local DNS Specification)
  - Existing RUDP Server implementation components.

constraints:
  - DO NOT use `http.server` or TCP sockets.
  - Server listens on port 8053 using the custom `RUDPServerTransport` (or equivalent RUDP server class).
  - Responses must be strictly formatted as valid HTTP 1.1 JSON responses.

steps:

  - step: 1️⃣ Create DNS Cache
    actions:
      - Create `server/dns/dns_cache.py`.
      - Implement a thread-safe `DNSCache` class mapping domain names to IPs + TTL expirations.
      - Add a default seed record: `agent.local -> 127.0.0.1` (TTL 300).
    acceptance_criteria:
      - Cache stores, retrieves, and expires records correctly based on TTL.

  - step: 2️⃣ Implement the DoH over RUDP Server
    actions:
      - Create `server/dns_server.py`.
      - Define a class `DoHRUDPServer` that instantiates the `DNSCache`.
      - Initialize an instance of your custom RUDP Server adapter bound to `127.0.0.1` port `8053`.
      - Create a listener loop:
        1. Receive data via the RUDP transport.
        2. Decode the bytes to an HTTP string.
        3. Parse the HTTP GET line to extract the `name` parameter from `/dns-query?name=...`.
        4. Query the `DNSCache`.
        5. Construct a raw HTTP response string (e.g., `HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": 200, "data": {"ip": "...", "ttl": ...}}`). If not found, return HTTP 404.
        6. Send the encoded string back via the RUDP transport.
    acceptance_criteria:
      - Server successfully processes HTTP strings over the RUDP layer.

  - step: 3️⃣ Orchestrator Integration
    actions:
      - Modify `server/__main__.py`.
      - Add `--dns-only` argparse flag.
      - When `--all` or `--dns-only` is provided, instantiate and start the `DoHRUDPServer` in a background daemon thread (alongside DHCP and the Agent).
    acceptance_criteria:
      - The Server Orchestrator successfully runs the RUDP DoH server concurrently with other services.