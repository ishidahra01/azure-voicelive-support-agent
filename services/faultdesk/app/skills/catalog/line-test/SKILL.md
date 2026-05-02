---
name: line-test
description: Run and interpret remote line tests. Use after identity is verified when symptoms suggest line trouble or technical diagnosis is required.
license: MIT
compatibility: Requires the faultdesk backend tools run_line_test and get_current_context.
metadata:
  owner: faultdesk
  version: "1.0"
---

# Line Test

Use this skill to execute a remote line test and explain the result.

## Procedure

1. Call `get_current_context` and confirm `identity.customer_id` is available.
2. If no customer ID is available, ask for identity verification rather than running a test.
3. Call `run_line_test` with `customer_id` and `test_type=basic` unless a different test is explicitly required.
4. Explain whether the line looks normal or abnormal.
5. If the recommended action is dispatch, move toward visit scheduling.

## Response Rules

- Warn the caller that a line test may take a short moment before running it.
- Summarize the result without raw metrics unless the caller asks.
- If the line is normal, suggest device reset or indoor equipment checks.
- If the line is abnormal, explain that a technician visit may be needed.