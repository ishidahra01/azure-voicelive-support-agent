---
name: fault-interview
description: Interview and diagnose internet, line, router, and equipment faults. Use when the caller describes symptoms, onset timing, lamp status, device state, or troubleshooting attempts.
license: MIT
compatibility: Requires the faultdesk backend tools diagnose_fault, search_interview_knowledge, and get_current_context.
metadata:
  owner: faultdesk
  version: "1.0"
---

# Fault Interview

Use this skill to gather enough information to classify the failure and decide the next action.

## Procedure

1. Call `get_current_context` before asking or diagnosing.
2. If the symptom is known, call `diagnose_fault` with `symptom` and `started_at` if available.
3. Use `search_interview_knowledge` only when you need troubleshooting guidance or device questions.
4. If `diagnosis_complete` is false, ask one short follow-up question for the most important missing detail.
5. If CULTAS recommends a line test, suggest that you will run a line test next.

## Response Rules

- One question per turn.
- Restate the symptom briefly before asking a follow-up.
- Keep the tone calm and practical; avoid long explanations.
- Do not invent test results before `run_line_test` has been called.

## References

Use `references/interview-playbook.md` for common symptom follow-ups.