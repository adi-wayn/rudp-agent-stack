---
description: Produce full test suite covering all subsystems.
---

# Workflow: generate_tests_suite
description: Produce full test suite covering all subsystems.

steps:
1. Collect all module entry points (DHCP, DNS, TCP, RUDP, App Server).
2. For each entry point, generate:
   - Unit tests (happy path, edge cases)
   - Mocked network layer tests
3. Create cross-subsystem integration tests.
4. Create stress tests simulating:
   - Random packet loss
   - Latency/jitter
   - High congestion
5. Produce reference PCAPs demonstrating expected flow.
6. Summarize test coverage and highlight remaining gaps.