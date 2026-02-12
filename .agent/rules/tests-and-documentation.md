---
trigger: always_on
---

# Testing and Documentation Rules

* Every new feature must include related unit tests.
* Tests must cover:
  - Happy paths
  - Error conditions
  - Edge cases (timeouts, out-of-order, duplicates)
* Integration tests must span:
  - DHCP → DNS → Application flows
  - TCP baseline
  - Reliable UDP behaviors
* Include reference PCAP captures that validate expected behavior.
* Document code with inline comments explaining decision logic.