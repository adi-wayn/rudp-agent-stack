---
trigger: always_on
---

# Project Basics Rules

# Coding & Architecture
* Always generate Python code following PEP8 and include docstrings.
* Use classes and modules, avoid global state.
* Functions must have clear name, inputs, outputs, and error semantics.
* All network code must include explicit parsing and framing logic.

# Error & Edge Handling
* All inbound fields must be validated.
* Disallowed operations must return correct error codes (400/403/404/409/413/500).
* Never assume correct data; defensive programming required.

# Modularity
* Separate components (DHCP, DNS, App Server, RUDP, Client) into modules.
* Shared utilities (serialization, logging, timers) in common module.