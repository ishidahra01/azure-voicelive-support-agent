# Skills Catalog

## Overview

Skills are independent Microsoft Agent Framework ChatAgents that handle specific business logic tasks. Each skill:
- Has a dedicated system prompt and tools
- Maintains its own AgentThread context (isolated per call_id × skill_name)
- Returns structured results + conversational text
- Never directly handles audio I/O (invoked via orchestrator tools)

## Skill Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Voice Live Orchestrator                                     │
│  "verify_identity" tool called                               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ IdentitySkill (Microsoft Agent Framework ChatAgent)        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ System Prompt: "You are an identity verification   │   │
│  │ specialist..."                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Tools:                                               │   │
│  │  - sf113_get_customer(customer_id)                  │   │
│  │  - sf113_fuzzy_match_name(name, customer_record)    │   │
│  │  - sf113_verify_address(address, customer_record)   │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ AgentThread (persisted by call_id + "identity")     │   │
│  └─────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Return to Orchestrator                                       │
│  Structured: {"verified": true, "customer_record": {...}}   │
│  Conversational: "ご本人確認できました。山田太郎様ですね。"    │
└─────────────────────────────────────────────────────────────┘
```

## Skills List

### 1. IdentitySkill

**Purpose**: Verify customer identity against account database.

**Input Parameters**:
```python
{
    "customer_id": str,        # 8-digit ID (optional)
    "name": str,               # Customer name (optional)
    "address": str,            # Address (optional)
    "phone": str               # Phone number (optional)
}
```

**Output (Structured)**:
```python
{
    "verified": bool,
    "confidence": float,       # 0.0-1.0
    "customer_record": {
        "customer_id": str,
        "name": str,
        "address": str,
        "phone": str,
        "contract_type": str
    },
    "verification_method": str,  # "customer_id", "name_address", "phone"
    "attempts": int
}
```

**Output (Conversational)**:
```
"ご本人確認できました。山田太郎様、東京都渋谷区のご住所でお間違いございませんでしょうか。"
```

**Internal Tools**:
- `sf113_get_customer(customer_id)` - Retrieve customer record by ID
- `sf113_fuzzy_match_name(name, candidates)` - Fuzzy name matching
- `sf113_verify_address(address, customer_record)` - Address verification

**Business Logic**:
- Try customer_id first (fastest, most reliable)
- Fall back to name + address combination
- Phone number as last resort
- Max 3 verification attempts before escalation
- Partial matches require confirmation

**AgentThread Context**:
- Stores verification attempts
- Stores candidate matches for disambiguation
- Preserves conversation if customer needs to retrieve ID

---

### 2. InterviewSkill

**Purpose**: Gather detailed fault information through guided questions.

**Input Parameters**:
```python
{
    "symptom": str,            # Initial symptom description (optional)
    "started_at": str,         # When fault started (optional)
    "context": dict            # Any additional context
}
```

**Output (Structured)**:
```python
{
    "fault_symptom": str,
    "fault_started_at": str,   # ISO format or relative ("3日前")
    "indoor_env": {
        "router_model": str,
        "lights_status": dict,  # {"power": "on", "wan": "off", ...}
        "connection_type": str,  # "有線" or "無線"
        "other_devices": list
    },
    "suspected_cause": str,    # "line", "router", "onu", "indoor_wiring"
    "urgency": str,            # "high", "medium", "low"
    "diagnosis_complete": bool
}
```

**Output (Conversational)**:
```
"承知いたしました。インターネットが3日前から繋がらない状況ですね。
ルーターのランプ状態を確認させていただけますでしょうか。"
```

**Internal Tools**:
- `cultas_diagnose_symptom(symptom)` - AI-powered diagnosis
- `ai_search_interview_kb(query)` - Search interview knowledge base
- `cultas_get_device_info(customer_id)` - Retrieve device information

**Business Logic**:
- Progressive questioning based on symptom type
- Device-specific questions (router model determines questions)
- Severity classification affects urgency
- Integrates with LineTestSkill for diagnostics

---

### 3. LineTestSkill

**Purpose**: Execute remote line test and interpret results.

**Input Parameters**:
```python
{
    "customer_id": str,
    "test_type": str,          # "basic", "extended", "full"
    "context": dict            # Fault context from InterviewSkill
}
```

**Output (Structured)**:
```python
{
    "test_executed": bool,
    "test_id": str,
    "results": {
        "line_status": str,    # "ok", "ng", "degraded"
        "ng_segments": list,   # ["segment_a", "segment_b"]
        "snr": float,          # Signal-to-noise ratio
        "attenuation": float,
        "error_rate": float
    },
    "interpretation": str,     # "line_fault", "customer_equipment", "normal"
    "recommended_action": str  # "dispatch", "customer_reset", "monitor"
}
```

**Output (Conversational)**:
```
"回線試験を実施いたします。30秒ほどお待ちください。
...
試験の結果、回線に問題が検出されました。技術者による訪問修理が必要です。"
```

**Internal Tools**:
- `sf113_run_line_test(customer_id, test_type)` - Execute test
- `sf113_get_test_result(test_id)` - Poll for result
- `cultas_interpret_test(results)` - AI interpretation

**Business Logic**:
- Test takes 20-60 seconds (async operation)
- Inform customer about wait time
- Interpret results in context of symptoms
- Determine if visit is required

---

### 4. VisitScheduleSkill

**Purpose**: Retrieve and present available visit time slots.

**Input Parameters**:
```python
{
    "customer_id": str,
    "area_code": str,
    "urgency": str,            # "high", "medium", "low"
    "preferred_dates": list,   # Optional customer preferences
    "work_type": str           # "fault_repair", "installation", etc.
}
```

**Output (Structured)**:
```python
{
    "candidates": [
        {
            "slot_id": str,
            "date": str,           # "2026-05-02"
            "time_range": str,     # "09:00-12:00"
            "available": bool,
            "priority": int        # Lower = higher priority
        },
        ...
    ],
    "recommended_slot_id": str,    # Best slot based on urgency
    "earliest_available": str,
    "constraint_notes": str        # Any scheduling constraints
}
```

**Output (Conversational)**:
```
"訪問日程をご提案させていただきます。
明日5月2日の午前9時から12時、または午後2時から5時が空いております。
いずれかご都合よろしい時間帯はございますでしょうか。"
```

**Internal Tools**:
- `sf113_get_visit_slots(area_code, work_type, date_range)` - Query slots
- `cultas_filter_slots(slots, urgency)` - Apply business rules
- `ai_search_dispatch_kb(query)` - Dispatch knowledge base

**Business Logic**:
- High urgency: prioritize same-day or next-day
- Show top 3-5 slots only (avoid overwhelming customer)
- Consider customer's expressed preferences
- Include weekend slots if weekdays full

---

### 5. VisitConfirmSkill

**Purpose**: Confirm visit appointment and create dispatch order.

**Input Parameters**:
```python
{
    "customer_id": str,
    "slot_id": str,
    "customer_confirmation": str,  # Explicit "はい" or equivalent
    "notes": str                   # Any special notes
}
```

**Output (Structured)**:
```python
{
    "confirmed": bool,
    "dispatch_id": str,
    "visit_details": {
        "date": str,
        "time_range": str,
        "technician_name": str,  # If assigned
        "contact_phone": str,
        "estimated_duration": str
    },
    "confirmation_sent": bool,  # Email/SMS confirmation
    "error": str                # If confirmation failed
}
```

**Output (Conversational)**:
```
"かしこまりました。5月2日の午前9時から12時で手配いたしました。
手配番号はDS-123456です。
前日にSMSでご連絡させていただきます。"
```

**Internal Tools**:
- `sf113_book_visit(customer_id, slot_id)` - Create dispatch order
- `sf113_send_confirmation(dispatch_id, method)` - Send confirmation
- `cultas_update_dispatch_status(dispatch_id, status)` - Update status

**Business Logic**:
- Require explicit customer confirmation
- Double-check slot still available before booking
- Send confirmation via customer's preferred method
- Store dispatch_id in SlotStore for reference

---

### 6. HistorySkill

**Purpose**: Record interaction history to 113SF system.

**Input Parameters**:
```python
{
    "customer_id": str,
    "call_id": str,
    "summary": str,
    "resolution": str,
    "tags": list
}
```

**Output (Structured)**:
```python
{
    "history_id": str,
    "recorded_at": str,        # ISO timestamp
    "success": bool,
    "error": str
}
```

**Output (Conversational)**:
```
"本日の内容を記録いたしました。"
```

**Internal Tools**:
- `sf113_post_history(customer_id, history_data)` - Create history record
- `cultas_categorize_issue(summary)` - Auto-categorize for analytics

**Business Logic**:
- Automatically generate summary from SlotStore and call log
- Include dispatch_id if visit scheduled
- Tag with resolution type for analytics
- Silent operation (no customer interaction needed)

---

### 7. SummarizerSkill

**Purpose**: Summarize conversation history for context management.

**Input Parameters**:
```python
{
    "utterances": list,        # List of {role, text, timestamp}
    "max_length": int,         # Max characters in summary
    "style": str               # "concise", "detailed", "bullet_points"
}
```

**Output (Structured)**:
```python
{
    "summary": str,
    "key_points": list,
    "sentiment": str,          # "positive", "neutral", "negative"
    "urgency": str             # "high", "medium", "low"
}
```

**Output (Conversational)**:
- Not used (internal skill only)

**Internal Tools**:
- `oob_summarize(text, max_length)` - Call OOB Foundry
- `oob_extract_key_points(text)` - Extract bullet points

**Business Logic**:
- Called automatically when Voice Live context exceeds threshold
- Replaces old utterances with summary
- Preserves key information (customer ID, slot values)
- Used in handoff_init to summarize triage phase

---

## Skill Invocation Pattern

### From Orchestrator

```python
# In orchestrator tools.py
@register_tool(
    description="Verify customer identity",
    parameters={
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
            "name": {"type": "string"},
            "address": {"type": "string"}
        }
    }
)
async def verify_identity(customer_id: str = None, name: str = None, address: str = None):
    # Get or create skill instance
    skill = get_skill("identity", call_id=current_call_id())

    # Invoke skill
    result = await skill.execute({
        "customer_id": customer_id,
        "name": name,
        "address": address
    })

    # Update SlotStore with structured result
    update_slots("identity", result["structured"])

    # Return conversational text to Voice Live
    return result["conversational"]
```

### Skill Implementation

```python
# In skills/identity.py
from microsoft_agent_framework import ChatAgent, AgentThread

class IdentitySkill(ChatAgent):
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.thread = AgentThread.get_or_create(f"{call_id}:identity")

        super().__init__(
            system_prompt="""
            You are an identity verification specialist.
            Your goal is to verify the customer's identity using available information.
            Use the provided tools to query customer records and perform matching.
            Be polite and guide the customer if they don't have their ID handy.
            """,
            tools=[sf113_get_customer, sf113_fuzzy_match_name, sf113_verify_address],
            thread=self.thread
        )

    async def execute(self, params: dict) -> dict:
        # Skill-specific logic
        message = self._format_input_message(params)
        response = await self.complete(message)

        return {
            "structured": self._extract_structured(response),
            "conversational": self._extract_conversational(response)
        }
```

## Testing Skills

### Unit Tests

```python
def test_identity_skill_with_customer_id():
    skill = IdentitySkill(call_id="test_001")
    result = await skill.execute({"customer_id": "12345678"})

    assert result["structured"]["verified"] == True
    assert result["structured"]["customer_record"]["customer_id"] == "12345678"
    assert "山田太郎" in result["conversational"]
```

### Integration Tests

```python
def test_full_identity_phase():
    # Test orchestrator → skill → slot update flow
    orchestrator = create_test_orchestrator()
    await orchestrator.execute_tool("verify_identity", {"customer_id": "12345678"})

    # Check SlotStore updated
    assert slot_store.get("identity", "customer_id") == "12345678"
    assert slot_store.get("identity", "verification_status") == "verified"
```

## Implementation Files

- `services/faultdesk/app/skills/base.py` - Base skill class
- `services/faultdesk/app/skills/identity.py` - IdentitySkill
- `services/faultdesk/app/skills/interview.py` - InterviewSkill
- `services/faultdesk/app/skills/line_test.py` - LineTestSkill
- `services/faultdesk/app/skills/visit_schedule.py` - VisitScheduleSkill
- `services/faultdesk/app/skills/visit_confirm.py` - VisitConfirmSkill
- `services/faultdesk/app/skills/history.py` - HistorySkill
- `services/faultdesk/app/skills/summarizer.py` - SummarizerSkill
