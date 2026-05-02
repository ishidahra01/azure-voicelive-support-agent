# Phase + Slot Design

## Overview

The Phase + Slot system is a conversation management pattern that combines:
- **Phases**: High-level conversation stages (e.g., identity verification, fault diagnosis)
- **Slots**: Individual pieces of information that need to be collected within each phase

This design enables:
1. **Structured Progress**: Ensures all required information is collected
2. **Flexible Navigation**: Users can jump between topics naturally
3. **Persistent State**: Information persists across phase transitions
4. **Progress Tracking**: Clear visibility into what's been completed

## Design Principles

| Principle | Description |
|-----------|-------------|
| **Slot Persistence** | Once filled, slots remain filled even when jumping to other phases |
| **Phase Independence** | Each phase can be entered and exited multiple times |
| **Required vs Optional** | Slots marked as required must be filled before phase completion |
| **Validation** | Each slot has a validator function to ensure data quality |
| **Dynamic Instructions** | Phase and slot state injected into Voice Live instructions every turn |

## Phase Definitions (Faultdesk)

### 1. intake (Handoff Acknowledgment)

**Purpose**: Welcome customer after handoff and reconfirm their intent.

**Slots:**
```python
{
    "greeting_done": {
        "type": "bool",
        "required": True,
        "description": "Has greeted customer and acknowledged handoff"
    },
    "understood_intent": {
        "type": "bool",
        "required": True,
        "description": "Has confirmed understanding of customer's issue"
    }
}
```

**Entry Trigger**: Handoff from frontdesk

**Typical Duration**: 30-60 seconds

**Success Criteria**: Customer feels acknowledged and understood

### 2. identity (Customer Verification)

**Purpose**: Verify customer identity before accessing account information.

**Slots:**
```python
{
    "customer_id": {
        "type": "str",
        "required": True,
        "description": "8-digit customer ID",
        "validator": "is_8digit_number"
    },
    "name_match": {
        "type": "bool",
        "required": True,
        "description": "Customer name matches record"
    },
    "address_match": {
        "type": "bool",
        "required": True,
        "description": "Address matches record"
    },
    "contact_phone": {
        "type": "str",
        "required": True,
        "description": "Contact phone number",
        "validator": "is_phone_number"
    },
    "verification_status": {
        "type": "str",
        "required": True,
        "description": "Overall verification result",
        "values": ["verified", "failed", "escalated"]
    }
}
```

**Entry Trigger**:
- Automatic after `intake` phase
- Manual via `jump_to_phase("identity")` if customer mentions identity issues

**Exit Conditions**:
- `verification_status == "verified"` → Proceed to `interview`
- `verification_status == "failed"` after 3 attempts → Escalate to operator

**Skill Called**: `identity-verification` file-based Agent Skill via `SkillsProvider`

### 3. interview (Fault Diagnosis)

**Purpose**: Gather detailed information about the fault, perform diagnostics.

**Slots:**
```python
{
    "fault_symptom": {
        "type": "str",
        "required": True,
        "description": "Description of the problem"
    },
    "fault_started_at": {
        "type": "str",
        "required": True,
        "description": "When the problem started",
        "validator": "is_datetime_expression"
    },
    "indoor_env": {
        "type": "dict",
        "required": True,
        "description": "Indoor equipment information",
        "schema": {
            "router_model": "str",
            "lights_status": "str",
            "connection_type": "str"
        }
    },
    "line_test_result": {
        "type": "dict",
        "required": False,
        "description": "Result of remote line test"
    },
    "suspected_cause": {
        "type": "str",
        "required": False,
        "description": "Identified cause of fault",
        "values": ["line", "router", "onu", "indoor_wiring", "unknown"]
    },
    "diagnosis_complete": {
        "type": "bool",
        "required": True,
        "description": "Diagnosis has been completed"
    }
}
```

**Entry Trigger**:
- Automatic after `identity` phase
- Manual via `jump_to_phase("interview")` if customer mentions fault details

**Skills Called**: `fault-interview` and `line-test` file-based Agent Skills via `SkillsProvider`

**Complex Logic**:
- May require multiple rounds of questioning
- Line test may take 30-60 seconds
- Diagnosis may lead back to identity if account access needed

### 4. visit (Visit Scheduling)

**Purpose**: Propose visit slots and confirm appointment.

**Slots:**
```python
{
    "visit_required": {
        "type": "bool",
        "required": True,
        "description": "Whether on-site visit is needed"
    },
    "visit_candidates": {
        "type": "list",
        "required": True,
        "description": "List of available time slots",
        "item_schema": {
            "slot_id": "str",
            "date": "str",
            "time_range": "str",
            "available": "bool"
        }
    },
    "customer_preference": {
        "type": "dict",
        "required": False,
        "description": "Customer's preferred time"
    },
    "visit_confirmed": {
        "type": "dict",
        "required": True,
        "description": "Confirmed visit appointment",
        "schema": {
            "slot_id": "str",
            "date": "str",
            "time_range": "str",
            "notes": "str"
        }
    },
    "dispatch_id": {
        "type": "str",
        "required": True,
        "description": "Dispatch order ID"
    }
}
```

**Entry Trigger**:
- Automatic after `interview` phase (if `visit_required`)
- Skip if remote resolution possible

**Skills Called**: `visit-scheduling` file-based Agent Skill via `SkillsProvider`

**Business Rules**:
- Slots retrieved from dispatch system (CULTAS)
- Same-day slots prioritized for urgent cases
- Confirmation requires explicit customer agreement

### 5. closing (Call Wrap-Up)

**Purpose**: Confirm resolution, record history, provide closing information.

**Slots:**
```python
{
    "resolution_status": {
        "type": "str",
        "required": True,
        "description": "How the issue was resolved",
        "values": ["visit_scheduled", "remote_resolved", "escalated", "pending"]
    },
    "customer_satisfied": {
        "type": "bool",
        "required": True,
        "description": "Customer confirms satisfaction"
    },
    "history_recorded": {
        "type": "bool",
        "required": True,
        "description": "Interaction logged to 113SF"
    },
    "followup_needed": {
        "type": "bool",
        "required": False,
        "description": "Whether follow-up is needed"
    },
    "closing_complete": {
        "type": "bool",
        "required": True,
        "description": "Closing process completed"
    }
}
```

**Entry Trigger**:
- Automatic after `visit` phase confirmation
- Manual if customer wants to end call

**Skills Called**: `history-recording` file-based Agent Skill via `SkillsProvider`

**Exit Conditions**:
- `closing_complete == True` → End call with `session_end`

## Phase Transitions

### Transition Rules

```python
# All phases can transition to any other phase (full flexibility)
PHASE_TRANSITIONS = {
    "intake": ["identity", "interview", "visit", "closing"],
    "identity": ["intake", "interview", "visit", "closing"],
    "interview": ["intake", "identity", "visit", "closing"],
    "visit": ["intake", "identity", "interview", "closing"],
    "closing": ["intake", "identity", "interview", "visit"]  # Allow re-opening
}

# However, typical linear flow:
# intake → identity → interview → visit → closing
```

### Transition Triggers

1. **Automatic Transition**: When all required slots in current phase are filled
   ```python
   if all_required_slots_filled(current_phase):
       suggest_next_phase()
   ```

2. **Manual Transition**: Via `jump_to_phase(target_phase)` tool
   ```python
   # Agent detects customer wants to discuss something from another phase
   jump_to_phase("identity")  # e.g., customer says "実は住所が変わったんです"
   ```

3. **Conditional Transition**: Based on slot values
   ```python
   if slots["interview"]["visit_required"] == False:
       jump_to_phase("closing")  # Skip visit phase
   ```

### Transition Announcements

Agent should naturally announce transitions:
- "それでは、お客様の本人確認をさせていただきます" (→ identity)
- "かしこまりました。故障の状況を詳しくお聞かせください" (→ interview)
- "訪問日程をご提案させていただきます" (→ visit)
- "それでは、今回の内容を確認させていただきます" (→ closing)

## Slot Management

### Slot Status

```python
class SlotStatus(Enum):
    PENDING = "pending"      # Not yet filled
    FILLED = "filled"        # Successfully filled
    INVALID = "invalid"      # Failed validation
    OPTIONAL = "optional"    # Optional, not filled
```

### Slot Validation

Each slot type has a validator:

```python
SLOT_VALIDATORS = {
    "customer_id": lambda v: v.isdigit() and len(v) == 8,
    "phone_number": lambda v: re.match(r"^[\d\-+()]+$", v),
    "datetime_expression": lambda v: parse_datetime(v) is not None,
    ...
}
```

### Slot Filling Process

```
1. Agent asks for information
2. User responds
3. Extract value from transcript
4. Validate value
5. If valid → Mark as "filled", proceed
6. If invalid → Mark as "invalid", ask again
7. If still unclear → Call relevant Skill for clarification
```

## Dynamic Instructions Generation

Every turn, the orchestrator generates instructions including:

```python
def generate_instructions(phase_state, slot_store):
    template = """
あなたは故障手配窓口の担当者です。明るく丁寧に対応してください。

【現在のフェーズ】 {current_phase}

【このフェーズの未確定項目】
{pending_slots}

【既に確定済みの情報】
{filled_slots}

【ガイダンス】
- 未確定項目を自然な質問で一つずつ確認してください
- お客様が別の話題に移った場合は jump_to_phase を使用してください
- 情報が確定したら対応する Skill ツールを呼んでください
- 必須項目がすべて埋まったら、次のフェーズに進めるか確認してください

【引き継ぎサマリ】
{handoff_summary}
"""

    return template.format(
        current_phase=phase_state.current,
        pending_slots=format_pending_slots(phase_state, slot_store),
        filled_slots=format_filled_slots(slot_store),
        handoff_summary=get_handoff_summary()
    )
```

**Example Output:**
```
【現在のフェーズ】 interview

【このフェーズの未確定項目】
- fault_symptom: 故障の症状
- fault_started_at: いつから発生したか
- indoor_env: 室内の機器状況

【既に確定済みの情報】
[identity]
- customer_id: 12345678
- name_match: True (山田太郎様)
- contact_phone: 03-1234-5678
```

## UI Display

### Phase Badge

```typescript
<PhaseBadge
  currentPhase="interview"
  allPhases={["intake", "identity", "interview", "visit", "closing"]}
/>
```

Displays:
```
[✓ intake] [✓ identity] [● interview] [○ visit] [○ closing]
```

### Slot Checklist

```typescript
<SlotChecklist
  phase="interview"
  slots={[
    { name: "fault_symptom", status: "filled", value: "ネット不通" },
    { name: "fault_started_at", status: "pending", required: true },
    { name: "indoor_env", status: "pending", required: true },
    { name: "line_test_result", status: "optional", required: false }
  ]}
/>
```

Displays:
```
Interview Phase Progress
☑ fault_symptom: ネット不通
☐ fault_started_at (required)
☐ indoor_env (required)
◇ line_test_result (optional)
```

## State Persistence

### SlotStore Structure

```python
{
  "call_id": "call_abc123",
  "phases": {
    "intake": {
      "greeting_done": {"status": "filled", "value": True},
      "understood_intent": {"status": "filled", "value": True}
    },
    "identity": {
      "customer_id": {"status": "filled", "value": "12345678"},
      "name_match": {"status": "filled", "value": True},
      ...
    },
    "interview": {
      "fault_symptom": {"status": "filled", "value": "ネット不通"},
      "fault_started_at": {"status": "pending", "value": None},
      ...
    }
  },
  "updated_at": "2026-05-01T03:15:30.123Z"
}
```

### Persistence Strategy

- **In-Memory**: During active call (SlotStore class)
- **On-Disk**: Exported to JSON at call end (CallLog)
- **Database**: Optional for analytics (future enhancement)

## Testing Strategy

### Unit Tests

- Slot validation functions
- Phase transition logic
- Instruction generation
- Slot filling/retrieval

### Integration Tests

- Full phase progression
- Jump between phases
- Slot persistence across jumps
- Error handling (invalid values)

### User Scenarios

1. **Happy Path**: Linear progression through all phases
2. **Back-and-Forth**: Jump to identity mid-interview, return to interview
3. **Validation Errors**: Invalid customer ID, retry logic
4. **Early Exit**: Customer wants to end call during interview

## Implementation Files

- `services/faultdesk/app/phases/definitions.py` - Phase and slot definitions
- `services/faultdesk/app/slots/schema.py` - Slot schema and validation
- `services/faultdesk/app/slots/store.py` - SlotStore implementation
- `services/faultdesk/app/orchestrator/phase_state.py` - Phase state management
- `services/faultdesk/app/orchestrator/instructions.py` - Dynamic instruction generation
