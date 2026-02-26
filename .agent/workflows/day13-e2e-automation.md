---
description: Implement Automated End-to-End Testing with Network Loss Simulation (Day 13).
---

---
description: Implement Automated End-to-End Testing with Network Loss Simulation (Day 13).
---

# Workflow: day13_e2e_automation

description: >
  Create an automated, headless End-to-End (E2E) test harness that executes the entire 
  Day 1-12 flow: DHCP -> DNS -> RUDP Agent. This script must inject network failures 
  (packet loss) to prove the reliability of the custom L4 RUDP transport. 
  Crucially, the test harness must run without `sudo` privileges so it can be executed 
  and analyzed autonomously by the AI agent.

goal:
  Produce `scripts/auto_e2e_runner.py`. The script will spawn the necessary server components 
  on unprivileged ports (e.g., > 1024), execute the client-side DORA process, resolve the DoH 
  address, and transfer application data over a lossy RUDP connection, validating the final state.

inputs:
  - `client.dhcp_client.DHCPClient`
  - `client.dns_client.DNSClient`
  - `client.transport.rudp_client.RUDPClientTransport`
  - `simulations.failure_engine.FailureEngine`
  - Server components (DHCP, DoH, Agent)

constraints:
  - **No Sudo:** All server and client components in this test must use configurable, unprivileged ports (e.g., DHCP on 6767/6868, DNS on 8054, App on 8081).
  - The script must self-contain the server setup (e.g., running servers in background Daemon threads).
  - Must inject a `FailureEngine` with at least 20% packet loss into the client-side RUDP connection to the App Server.
  - Must assert that the final application data (e.g., file list or downloaded file) is exactly as expected, proving successful retransmissions.

steps:

  - step: 1️⃣ Refactor for Unprivileged Port Configuration
    actions:
      - Ensure the `DHCPServer` and `DHCPClient` accept custom ports (override 67/68 defaults).
      - Ensure the `DoHRUDPServer` and `DNSClient` accept custom ports.
      - Ensure the Agent Server and `RUDPClientTransport` accept custom ports.
    acceptance_criteria:
      - All networking components can be instantiated with arbitrary ports without hardcoded privileged port restrictions.

  - step: 2️⃣ Create the Automated E2E Test Harness
    actions:
      - Create `scripts/auto_e2e_runner.py`.
      - **Setup:** Start the DHCP, DNS, and App servers on unprivileged ports in background threads.
      - **Phase 1 (DHCP):** Run `DHCPClient` on the unprivileged ports. Assert a virtual IP is acquired.
      - **Phase 2 (DNS):** Run `DNSClient`. Assert `agent.local` resolves to the server's virtual IP.
      - **Phase 3 (Agent over Lossy RUDP):** - Instantiate `RUDPClientTransport` connecting to the App Server.
          - Inject `FailureEngine(drop_rate=0.20, latency_ms=10)`.
          - Send an App-layer request (e.g., `LIST` or `GET`).
      - **Validation:** Assert the response is complete and not corrupted. Log the success, specifically noting that retransmissions must have occurred to overcome the 20% loss.
      - **Teardown:** Cleanly shut down all background server threads.
    acceptance_criteria:
      - The script runs from start to finish without hanging, successfully verifying the entire stack's resilience against 20% packet loss.

  - step: 3️⃣ Autonomous Execution & Analysis
    actions:
      - The AI Agent must execute `scripts/auto_e2e_runner.py` directly using its code execution tools.
      - The Agent must analyze the standard output/logs to verify that the test passed and summarize the findings.
    acceptance_criteria:
      - A detailed summary report is provided based on the actual run of the E2E script.