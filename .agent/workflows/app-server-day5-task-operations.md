---
description: Implement TASK opcodes and planner logic.
---

# Workflow: app_server_day5_task_operations
description: Implement TASK opcodes and planner logic.

goal:
Add rule-based Agent task execution.

steps:

1. Read TASK execution state machine.
2. Implement Planner:
   - Map task_type → handler
   - Decide streaming vs in-memory processing

3. Implement TASK handlers:
   - SEARCH_REPORT
   - FILTER_LINES
   - HASH_AND_STORE

4. Artifact handling:
   - If output > threshold → store artifact file
   - Return preview + artifact reference

5. Integrate with PolicyGuard:
   - Enforce execution limits
   - Enforce size limits

6. Logging:
   - task_type
   - execution_time
   - result_size

7. Tests:
   - SEARCH_REPORT valid
   - FILTER_LINES valid
   - HASH_AND_STORE valid
   - Large output artifact generation

definition_of_done:
- All TASK types working
- Planner routing correct
- Artifact logic functional