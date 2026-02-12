---
trigger: always_on
---

# Protocol & Security Rules

* All messages must adhere to the defined application binary header.
* Validate checksum for Reliable UDP packets before processing.
* Reject and log packets with invalid framing or malformed headers.
* Prevent path traversal and enforce sandbox for file paths.
* Sanitize all task payload fields (e.g., no unbounded maps/arrays).
* Use secure defaults for timeouts, buffer limits, and connection cleanup.