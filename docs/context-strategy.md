# Context Management Strategy

## Overview

The context management strategy defines how conversation state, customer information, and business data flow through the system across multiple layers. Proper context management is critical for:
- Maintaining coherent conversations
- Avoiding information loss during handoffs
- Preventing context overflow in Voice Live
- Enabling skill-specific context isolation
- Supporting debugging and analytics

## Context Layers

### Layer 1: Voice Live Conversation History

**Location**: Voice Live session + `context/call_log.py`

**Content**:
- User utterances (transcribed speech)
- Assistant responses (generated text + audio)
- Function call records (tool name, arguments, results)
- Session events (phase changes, errors)

**Size Management**:
- Voice Live has a context window limit (~128K tokens for gpt-4o-realtime)
- Old utterances summarized when approaching limit
- Summarization triggered at 80% capacity
- Recent 10-15 exchanges kept verbatim

**Flow to Voice Live**:
- **Flowing**: All utterances and responses flow naturally
- **Summarization**: Old content replaced with summaries via SummarizerSkill
- **Injection Point**: Via session update, not in instructions

**Example**:
```
[Turn 1]
User: インターネットが繋がらないんです
Assistant: 承知いたしました。お客様番号を教えていただけますか

[Turn 2]
User: 12345678です
Assistant: ありがとうございます。山田太郎様ですね

... (10 more turns) ...

[Turn 13 - After Summarization]
Summary: Customer reported internet outage. Identity verified (ID: 12345678, 山田太郎様).
         Fault occurred 3 days ago. Router lights: power=on, wan=off.

[Turn 14]
User: いつ修理に来ていただけますか
Assistant: ...
```

---

### Layer 2: SlotStore (Persistent Structured State)

**Location**: `slots/store.py`

**Content**:
- All slot values across all phases
- Slot status (pending/filled/invalid)
- Validation errors
- Update timestamps

**Persistence**:
- In-memory during call (Python dict)
- Exported to JSON at call end
- Optionally stored in database for analytics

**Flow to Voice Live**:
- **Not flowing** directly into conversation history
- **Injected into instructions** every turn
- Appears in system prompt as structured data

**Injection Method**:
```python
def update_instructions(current_phase, slot_store):
    instructions = f"""
    You are a fault desk agent.

    Current Phase: {current_phase}

    Confirmed Information:
    {format_filled_slots(slot_store)}

    Pending Information:
    {format_pending_slots(current_phase, slot_store)}

    Your task: Collect pending information through natural conversation.
    """

    session.update(instructions=instructions)
```

**Example Injection**:
```
Confirmed Information:
[identity]
- customer_id: 12345678
- name_match: True (山田太郎様)
- contact_phone: 03-1234-5678

[interview]
- fault_symptom: インターネット不通
- fault_started_at: 3日前

Pending Information (interview phase):
- indoor_env: 室内機器の状況 (required)
- line_test_result: 回線試験結果 (optional)
```

---

### Layer 3: Skill-Specific AgentThreads

**Location**: Microsoft Agent Framework `AgentThread` (per call_id × skill_name)

**Content**:
- Skill-internal conversation history
- Tool calls made by skill
- Intermediate reasoning steps
- Partial results

**Isolation**:
- Each skill has its own thread
- Threads are isolated from each other
- Threads are isolated from Voice Live main context
- Threads persist across skill invocations within same call

**Flow to Voice Live**:
- **Not flowing**: Skill internals never exposed to Voice Live
- **Only final results flow**: Structured output + conversational summary

**Example**:
```
[IdentitySkill Thread for call_abc123]

Turn 1:
System: You are an identity verification specialist...
User: Verify customer with ID 12345678
Assistant: Let me query the customer database.
Tool: sf113_get_customer(12345678)
Result: {name: "山田太郎", address: "東京都..."}

Turn 2:
User: Does name "山田太郎" match?
Assistant: Yes, exact match confirmed.

[This internal dialogue never reaches Voice Live orchestrator]
[Only returned: {"verified": True, "customer_record": {...}}]
```

---

### Layer 4: Business API Logs

**Location**: `adapters/*.py` + structured logs

**Content**:
- Raw API requests to 113SF, CULTAS, AI Search
- Raw API responses (complete payload)
- API latency and error details
- Retry attempts and outcomes

**Purpose**:
- Audit trail for external system interactions
- Debugging integration issues
- Performance monitoring
- Compliance and security logging

**Flow to Voice Live**:
- **Never flows**: Too verbose and not relevant to conversation
- **Logged separately**: Structured JSON logs with call_id correlation

**Example Log Entry**:
```json
{
  "timestamp": "2026-05-01T03:15:30.123Z",
  "call_id": "call_abc123",
  "adapter": "sf113",
  "method": "get_customer",
  "request": {"customer_id": "12345678"},
  "response": {
    "customer_id": "12345678",
    "name": "山田太郎",
    "address": "東京都渋谷区...",
    "contract_type": "fiber"
  },
  "latency_ms": 245,
  "success": true
}
```

---

### Layer 5: Phase Transition History

**Location**: `orchestrator/phase_state.py`

**Content**:
- Phase transition log (from → to)
- Transition triggers (tool call, manual jump, auto progression)
- Timestamps
- Transition reasons

**Purpose**:
- UI display (phase badge timeline)
- Analytics (average time per phase)
- Debugging conversation flow
- Understanding user behavior patterns

**Flow to Voice Live**:
- **Not flowing** into conversation
- **Not in instructions** (only current phase shown)
- **Sent to frontend** via `phase_changed` messages

**Example**:
```python
phase_transitions = [
    {
        "from": None,
        "to": "intake",
        "trigger": "handoff_init",
        "timestamp": "2026-05-01T03:12:35.000Z"
    },
    {
        "from": "intake",
        "to": "identity",
        "trigger": "auto_progression",
        "timestamp": "2026-05-01T03:13:10.000Z"
    },
    {
        "from": "identity",
        "to": "interview",
        "trigger": "tool:verify_identity",
        "timestamp": "2026-05-01T03:14:30.000Z"
    }
]
```

---

### Layer 6: Call Logs (Complete Call Record)

**Location**: `context/call_log.py` → JSON export

**Content**:
- Complete conversation transcript
- All slot values (final state)
- Phase transition history
- Tool call log (all tools with results)
- Handoff information
- Call metadata (duration, outcome, etc.)

**Export Format**:
```json
{
  "call_id": "call_abc123",
  "started_at": "2026-05-01T03:12:30.000Z",
  "ended_at": "2026-05-01T03:20:15.000Z",
  "duration_sec": 465,
  "services": ["frontdesk", "faultdesk"],
  "triage_summary": "インターネット故障",
  "final_outcome": "visit_scheduled",

  "transcript": [
    {"timestamp": "...", "role": "user", "text": "..."},
    {"timestamp": "...", "role": "assistant", "text": "..."},
    ...
  ],

  "phase_transitions": [...],

  "slots": {
    "identity": {...},
    "interview": {...},
    "visit": {...},
    "closing": {...}
  },

  "tool_calls": [
    {
      "timestamp": "...",
      "tool": "verify_identity",
      "arguments": {...},
      "result": {...}
    },
    ...
  ],

  "metadata": {
    "customer_id": "12345678",
    "dispatch_id": "DS-123456",
    "history_id": "H-789012"
  }
}
```

**Purpose**:
- Post-call analysis
- Quality assurance
- Training data for model improvement
- Customer service records
- Compliance audit trail

**Storage**:
- Local JSON files (development)
- Azure Blob Storage (production)
- Optional: Azure Table Storage for queryability

---

## Context Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Voice Live Session                                              │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Conversation History (L1)                                   │ │
│ │ - Recent 10-15 turns verbatim                               │ │
│ │ - Older turns summarized                                    │ │
│ │ - Max ~100K tokens                                          │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Dynamic Instructions (updated every turn)                   │ │
│ │ - Current phase                                             │ │
│ │ - SlotStore snapshot (L2) ← INJECTED                        │ │
│ │ - Pending requirements                                      │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Tool call: verify_identity()
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Skill (e.g., IdentitySkill)                                     │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ AgentThread (L3) - Isolated context                         │ │
│ │ - Skill-specific conversation                               │ │
│ │ - Not visible to Voice Live                                 │ │
│ └─────────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Skill Tools                                                 │ │
│ │ - Call adapters (L4)                                        │ │
│ │ - Log API requests/responses                                │ │
│ └─────────────────────────────────────────────────────────────┘ │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 │ Return: {structured, conversational}
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator                                                     │
│ - Update SlotStore (L2) with structured result                  │
│ - Update PhaseState (L5) if phase transition                    │
│ - Append to CallLog (L6)                                        │
│ - Return conversational text to Voice Live                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summarization Strategy

### When to Summarize

Trigger summarization when:
1. Voice Live context size > 80% of limit (~100K tokens)
2. Call duration > 20 minutes (proactive)
3. Before phase transition (optional, for clean phase boundaries)

### What to Summarize

Summarize:
- User utterances older than 15 turns
- Assistant responses older than 15 turns
- Tool call results (keep tool names, summarize arguments/results)

Preserve verbatim:
- Last 10-15 turns
- Current phase slot discussion
- Any unresolved questions or pending clarifications

### Summarization Process

```python
async def summarize_context_if_needed(session, call_log):
    if session.token_count > THRESHOLD:
        # Get old utterances (beyond last 15 turns)
        old_utterances = call_log.get_utterances(end_index=-15)

        # Call SummarizerSkill
        skill = SummarizerSkill(call_id)
        summary_result = await skill.execute({
            "utterances": old_utterances,
            "max_length": 500,
            "style": "concise"
        })

        # Replace old utterances with summary
        summary_message = {
            "role": "system",
            "content": f"Previous conversation summary: {summary_result['summary']}"
        }

        # Update session (remove old, add summary)
        await session.truncate_and_summarize(
            keep_recent=15,
            summary=summary_message
        )
```

---

## Handoff Context Transfer

### Frontdesk → Faultdesk

Only essential information transferred:

```python
handoff_init_message = {
    "call_id": call_id,
    "triage_summary": summarize_triage_conversation(),  # Use SummarizerSkill
    "caller_attrs": {
        "phone_number": extracted_from_caller_id,
        "area_code_hint": "03"  # Hint for dispatch scheduling
    },
    "source_phase": "triage",
    "context": {
        "sentiment": analyze_sentiment(),
        "urgency": classify_urgency()
    }
}
```

**NOT transferred**:
- Full conversation transcript (too large, not needed)
- Voice Live session state (new session created)
- Frontdesk-specific context

**Why**: Clean slate for faultdesk, avoid context pollution

---

## Best Practices

### 1. Keep Voice Live Context Lean

- Don't inject large structured data into conversation history
- Use instructions injection for structured state (SlotStore)
- Summarize aggressively to stay under limits

### 2. Isolate Skill Context

- Never leak skill internals to Voice Live
- Skills should be black boxes with clean input/output
- Use AgentThread per skill to prevent cross-contamination

### 3. Log Everything Separately

- Business API calls logged independently (L4)
- Call logs exported after call completes (L6)
- Don't pollute Voice Live context with logging data

### 4. Structure Over Prose

- SlotStore uses structured data (dict), not prose
- Instructions reference slots by name
- Reduces token usage and improves reliability

### 5. Correlation IDs

- Use call_id to correlate across all layers
- Enable debugging across services
- Support analytics and auditing

---

## Implementation Files

- `services/faultdesk/app/context/thread_store.py` - AgentThread management
- `services/faultdesk/app/context/call_log.py` - Call log accumulation & export
- `services/faultdesk/app/slots/store.py` - SlotStore implementation
- `services/faultdesk/app/orchestrator/phase_state.py` - Phase transition tracking
- `services/faultdesk/app/skills/summarizer.py` - Summarization skill
- `packages/voiceshared/voicelive/session.py` - Context size monitoring
