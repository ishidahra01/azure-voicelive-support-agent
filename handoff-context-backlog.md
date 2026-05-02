# Handoff and Context Backlog

This backlog captures follow-up work for Voice Live session switching and context transfer between Frontdesk and specialized desk agents.

## Current Implementation Summary

- The browser keeps a single WebSocket connection to Frontdesk (`/ws/voice`).
- Frontdesk creates the first Voice Live session for triage.
- When `route_to_fault_desk` is called, Frontdesk closes its Voice Live session and opens a service-to-service WebSocket to Faultdesk (`/ws/desk`).
- Faultdesk creates a new Voice Live session with its own instructions, tools, `PhaseState`, `SlotStore`, and `CallLog`.
- The current context transfer is summary-based: `call_id`, `triage_summary`, `caller_attrs`, and `source_phase` are sent via `handoff_init`.
- Full conversation history, transcript turns, and structured triage state are not yet transferred.

## Backlog Items

### HC-001: Make Handoff Cutover Two-Phase

**Priority:** High

**Problem:** Frontdesk currently closes the triage Voice Live session before confirming that Faultdesk accepted the handoff. If Faultdesk connection or initialization fails, the caller can lose the active Voice Live session.

**Desired Behavior:** Keep the Frontdesk Voice Live session alive until Faultdesk returns `handoff_ack.ready = true`. After ack, switch the browser audio path to Faultdesk and then close the Frontdesk Voice Live session.

**Acceptance Criteria:**

- Faultdesk WebSocket connection failure leaves the Frontdesk Voice Live session usable.
- `handoff_status: initiating` is followed by either `connected` or a recoverable error.
- Frontdesk closes its Voice Live session only after successful `handoff_ack`.
- Smoke test covers a successful handoff and a simulated Faultdesk unavailable case.

### HC-002: Use `HandoffInitMessage.context` for Structured Context Transfer

**Priority:** High

**Problem:** `HandoffInitMessage` already has an optional `context` field, but Frontdesk does not populate it. Faultdesk receives only `triage_summary` and `caller_attrs`.

**Desired Behavior:** Populate `context` with structured data that lets the receiving desk continue the call without re-asking known information.

**Suggested Payload:**

```json
{
  "recent_turns": [
    {"role": "user", "text": "..."},
    {"role": "assistant", "text": "..."}
  ],
  "triage_slots": {
    "intent": "fault",
    "symptom": "...",
    "device": "...",
    "customer_id": "..."
  },
  "tool_results": [],
  "handoff_reason": "fault_detected"
}
```

**Acceptance Criteria:**

- Frontdesk stores recent transcript turns during triage.
- `HandoffManager.initiate_handoff` accepts and sends a context payload.
- Faultdesk reads `handoff_msg.context` and stores it in its session state.
- Context is included in Faultdesk initial instructions in a concise, safe form.

### HC-003: Seed Faultdesk SlotStore from Triage Context

**Priority:** High

**Problem:** Faultdesk starts with an empty `SlotStore`, even when Frontdesk already knows useful facts such as customer ID, symptom, device, phone number, or area hint.

**Desired Behavior:** Map structured triage fields into Faultdesk slots at handoff time.

**Candidate Mappings:**

- `caller_attrs.customer_id` -> `identity.customer_id`
- `caller_attrs.phone_number` -> `identity.contact_phone`
- `caller_attrs.area_code_hint` -> `visit.area_code`
- `triage_slots.symptom` -> `interview.fault_symptom`
- `triage_slots.device` -> `interview.indoor_env` or a dedicated device slot

**Acceptance Criteria:**

- Faultdesk `slots_snapshot` reflects seeded values immediately after handoff.
- Seeded values are marked as filled only when confidence is sufficient.
- Faultdesk does not ask again for information that was confidently seeded.

### HC-004: Add Conversation Turn Buffer in Frontdesk

**Priority:** Medium

**Problem:** Frontdesk logs transcripts but does not keep an in-memory recent-turn buffer for handoff context.

**Desired Behavior:** Maintain a bounded list of recent triage turns in Frontdesk session state.

**Implementation Notes:**

- Store both user and assistant final transcripts.
- Keep the most recent 10-15 turns or cap by character count.
- Exclude suppressed internal JSON and startup noise from the buffer.
- Include timestamps if useful for debugging.

**Acceptance Criteria:**

- Final user/assistant transcripts are appended to `session["recent_turns"]`.
- The buffer is bounded and cannot grow without limit.
- Handoff context includes the recent turns.

### HC-005: Generate a Safe Handoff Summary from Recent Turns

**Priority:** Medium

**Problem:** The handoff summary currently depends on the model-provided `route_to_fault_desk.summary`. That is useful but not independently verified or enriched.

**Desired Behavior:** Generate or validate a concise handoff summary from recent turns and known structured fields before sending to Faultdesk.

**Acceptance Criteria:**

- Summary includes user intent, symptom, known identifiers, and unresolved questions when available.
- Summary excludes internal tool JSON, raw backend payloads, and sensitive data not needed by the receiving desk.
- If summary generation fails, the existing tool-provided summary is used as fallback.

### HC-006: Optionally Replay Selected Conversation Items into Faultdesk Voice Live

**Priority:** Low

**Problem:** Faultdesk Voice Live receives context via instructions, not as prior conversation items. This is usually enough, but it may reduce conversational continuity.

**Desired Behavior:** Evaluate whether selected prior turns should be inserted into the new Voice Live conversation as context items, or whether instruction-based context remains preferable.

**Acceptance Criteria:**

- Prototype compares instruction-only context vs. selected-turn replay.
- No internal tool output or suppressed text is replayed.
- Decision is documented in an ADR before productionizing.

### HC-007: Document Session Lifecycle as an ADR

**Priority:** Medium

**Problem:** The session-switching contract is important enough to document as an architectural decision.

**Desired Behavior:** Add an ADR describing why browser WebSocket stays open while Voice Live sessions are replaced across desks.

**Acceptance Criteria:**

- ADR documents current lifecycle, failure modes, and recovery behavior.
- ADR states whether old Voice Live session closes before or after `handoff_ack`.
- ADR references `handoff-protocol.md` and `context-strategy.md`.

### HC-008: Add Handoff Failure and Recovery Tests

**Priority:** High

**Problem:** Current smoke tests cover successful handoff. Failure behavior is not covered.

**Desired Behavior:** Add automated tests for Faultdesk unavailable, bad `handoff_ack`, and Faultdesk disconnect during active call.

**Acceptance Criteria:**

- Test confirms Frontdesk reports a user-visible recoverable error on Faultdesk unavailable.
- Test confirms Frontdesk does not leave session state half-active.
- Test confirms audio/control routing remains consistent after failure.

### HC-009: Persist Handoff Context in Call Logs

**Priority:** Medium

**Problem:** Faultdesk call logs include `triage_summary`, but not the complete handoff context payload.

**Desired Behavior:** Save the received handoff context in Faultdesk call logs for debugging and audit.

**Acceptance Criteria:**

- Faultdesk call log JSON includes `handoff_context` when present.
- Sensitive fields are redacted or omitted according to logging policy.
- Existing `transcript` and `detailed_log` output remain unchanged.

## Suggested Implementation Order

1. HC-004: Add Frontdesk recent-turn buffer.
2. HC-002: Populate and consume `HandoffInitMessage.context`.
3. HC-003: Seed Faultdesk slots from structured context.
4. HC-001: Make the handoff cutover two-phase.
5. HC-008: Add failure and recovery tests.
6. HC-009: Persist handoff context in call logs.
7. HC-007: Write ADR for session lifecycle.
8. HC-005 and HC-006: Improve summary quality and evaluate optional replay.
