---
name: identity-verification
description: Verify caller identity for fault handling using customer ID, name, address, and contact details. Use during the identity phase or whenever customer identity slots must be confirmed before diagnostics or dispatch.
license: MIT
compatibility: Requires the faultdesk backend tools verify_identity and get_current_context.
metadata:
  owner: faultdesk
  version: "1.0"
---

# Identity Verification

Use this skill to confirm that the caller matches an SF113 customer record.

## Procedure

1. Call `get_current_context` to inspect already-filled slots.
2. If `customer_id` is available, call `verify_identity` with `customer_id` first.
3. If no customer ID is available, collect `name` and then `address`; call `verify_identity` with those values.
4. If verification succeeds, briefly confirm the customer and move on.
5. If verification fails, ask for exactly one missing or ambiguous field.

## Response Rules

- Keep customer-facing replies to 1-2 short Japanese sentences.
- Do not expose internal confidence scores, candidate lists, or raw backend JSON.
- Do not proceed to line tests or visit booking until identity is verified.

## Expected Slots

Read `references/slot-contract.md` for the slot names this skill updates.