---
name: history-recording
description: Summarize, categorize, and record faultdesk call history into SF113. Use near closing, before handoff, or whenever an auditable record is required.
license: MIT
compatibility: Requires the faultdesk backend tools summarize_call, record_history, and get_current_context.
metadata:
  owner: faultdesk
  version: "1.0"
---

# History Recording

Use this skill to produce and persist the service record for the call.

## Procedure

1. Call `get_current_context` to inspect customer ID and slot state.
2. If no summary is provided, call `summarize_call`.
3. Call `record_history` with `summary`, `customer_id` if known, and `resolution` when available.
4. If recording succeeds, tell the caller only that today's details have been recorded.
5. If recording fails due to missing customer ID, ask for customer identity or escalate.

## Response Rules

- Do not read internal tags, categories, or backend IDs aloud unless the caller asks.
- Keep closing acknowledgements to one sentence.
- The record should include symptom, test result, visit booking, and unresolved follow-up if available.