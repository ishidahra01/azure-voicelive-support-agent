---
name: visit-scheduling
description: Find, propose, and confirm technician repair visit slots. Use when diagnosis recommends dispatch or the caller needs an onsite repair appointment.
license: MIT
compatibility: Requires the faultdesk backend tools propose_visit_slots, confirm_visit, and get_current_context.
metadata:
  owner: faultdesk
  version: "1.0"
---

# Visit Scheduling

Use this skill to propose and confirm repair visit appointments.

## Procedure

1. Call `get_current_context` and gather `customer_id`, `area_code`, and urgency if available.
2. Call `propose_visit_slots` before presenting options.
3. Present at most three candidate slots.
4. After the caller chooses a slot, call `confirm_visit` with `customer_id` and `slot_id`.
5. Read back the confirmed date, time range, and dispatch ID.

## Response Rules

- Do not promise a visit time until `confirm_visit` succeeds.
- Keep option presentation compact.
- Ask the caller to choose one of the listed slots.
- If no slots are available, apologize and offer to search for another date range or escalate.

## References

Read `references/dispatch-faq.md` when the caller asks about visit duration, attendance, or notifications.