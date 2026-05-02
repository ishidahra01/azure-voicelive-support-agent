# Context Management Strategy

## Overview

This document describes how conversation history, handoff context, customer facts, and skill execution context are managed in the current implementation.

The core design decision is:

**Do not use Microsoft Agent Framework `AgentSession` as the long-term call memory.**

Instead, the system separates context by responsibility:

- Voice Live keeps the real-time conversational flow for the active desk.
- `PhaseState` tracks where the business process is.
- `SlotStore` is the source of truth for confirmed business facts.
- `CallLog` records what happened for audit, debugging, and later summarization.
- Microsoft Agent Framework (MAF) runs short-lived skill tasks with dynamic `SkillsProvider` loading.
- Handoff messages transfer only the context needed by the receiving desk.

This keeps voice interaction natural while making the business state explicit and recoverable.

## Source Of Truth

| Context Type | Source of Truth | Used For | Long-Lived? |
| --- | --- | --- | --- |
| Real-time conversation | Active Voice Live session | Natural turn-taking, interruption handling, assistant speech | Per desk session |
| Business phase | `PhaseState` | Current workflow phase and transition decisions | Per call |
| Confirmed facts | `SlotStore` | Identity, fault details, visit booking, closing state | Per call |
| Handoff facts | `handoff_init` fields and seeded slots | Continuing after frontdesk -> faultdesk | Per handoff / per call |
| Audit history | `CallLog` and saved JSON | Debugging, QA, post-call analysis | Exported at call end |
| Skill procedure context | MAF `SkillsProvider` + fresh `AgentSession` | Loading `SKILL.md`, choosing backend tools, producing a short result | Per skill task |
| Backend integration details | Adapter logs and tool-call results | Troubleshooting external systems | Logged separately |

## Context Layers

### Layer 1: Voice Live Session Context

**Purpose:** Maintain the real-time spoken conversation for the currently active desk.

**Current behavior:**

- Frontdesk creates a Voice Live session for triage.
- When routing to faultdesk succeeds, frontdesk closes its Voice Live session and bridges browser audio to faultdesk.
- Faultdesk creates a new Voice Live session with faultdesk-specific instructions and tools.
- Voice Live receives audio, emits transcripts, generates assistant audio, and calls registered tools.

**What belongs here:**

- Recent spoken turns for the active desk.
- Turn detection state.
- Assistant audio response state.
- Tool call decisions made by the real-time model.

**What does not belong here:**

- Raw backend API payloads.
- Long-term business state.
- Full call audit history.
- MAF skill-internal reasoning.

Voice Live context is treated as useful but not authoritative. If Voice Live forgets or summarizes something, the business state still comes from `SlotStore` and `PhaseState`.

### Layer 2: Handoff Context

**Purpose:** Move the minimum useful context from one desk service to another without carrying the entire Voice Live session.

**Current frontdesk -> faultdesk payload:**

```json
{
  "type": "handoff_init",
  "call_id": "call_abc123",
  "triage_summary": "インターネットがつながらない",
  "caller_attrs": {
    "phone_number": "+81-3-1234-5678",
    "area_code_hint": "03",
    "customer_id": null
  },
  "source_phase": "triage",
  "context": {},
  "timestamp": "2026-05-02T10:00:00Z"
}
```

**Faultdesk initialization from handoff:**

- Start the faultdesk workflow at `identity`, not `intake`.
- Mark intake facts as already completed.
- Seed `interview.fault_symptom` from `triage_summary` when available.
- Generate initial Voice Live instructions that explicitly say the handoff summary is known and should not be re-asked.

Example seeded state:

```json
{
  "current_phase": "identity",
  "slots": {
    "intake": {
      "greeting_done": true,
      "understood_intent": true
    },
    "interview": {
      "fault_symptom": "インターネットがつながらない"
    }
  }
}
```

This is why faultdesk should ask for the customer number next instead of asking, "What can I help you with?"

### Layer 3: PhaseState

**Purpose:** Track the current business phase and phase transitions.

Faultdesk uses the phase model:

```text
intake -> identity -> interview -> visit -> closing
```

In the current handoff path, faultdesk starts at `identity` because frontdesk has already completed the intake intent capture.

**What belongs here:**

- Current phase.
- Previous phase.
- Transition history.
- Transition triggers such as `handoff_init`, `tool_execution`, `auto_progression`, or manual phase jumps.

**How it flows:**

- Voice Live instructions include the current phase.
- The frontend receives `phase_changed` messages.
- MAF task prompts include the current phase through generated orchestrator instructions.
- Call logs include phase transitions.

Example transition record:

```json
{
  "from": "identity",
  "to": "interview",
  "trigger": "tool_execution",
  "timestamp": "2026-05-02T10:03:00Z"
}
```

### Layer 4: SlotStore

**Purpose:** Store confirmed business facts in structured form.

`SlotStore` is the most important durable context layer. The assistant should not infer the business truth from transcript prose when a slot exists.

**What belongs here:**

- Identity facts such as customer ID and verification status.
- Fault interview facts such as symptom, start time, suspected cause, and line-test results.
- Visit facts such as candidate slots, confirmed visit, and dispatch ID.
- Closing facts such as whether history was recorded.

**How it flows:**

- Voice Live instructions receive a concise snapshot of filled and pending slots.
- MAF backend tools update slots after external system calls.
- The frontend receives `slots_snapshot` messages for the active phase.
- Call logs export final slot state at call end.

Example after identity verification:

```json
{
  "identity": {
    "customer_id": "12345678",
    "name_match": true,
    "address_match": true,
    "contact_phone": "03-1234-5678",
    "verification_status": "verified"
  },
  "interview": {
    "fault_symptom": "インターネットがつながらない"
  }
}
```

Example instruction fragment generated from slots:

```text
【現在フェーズ】
identity

【全フェーズの確定済み情報】
- intake.greeting_done: true
- intake.understood_intent: true
- interview.fault_symptom: インターネットがつながらない

【identityフェーズの発話】
受付から用件は引き継ぎ済みです。故障内容の再確認ではなく、手配確認に必要なお客様番号を一つだけ質問してください。
```

### Layer 5: CallLog

**Purpose:** Record the call for audit, debugging, QA, and later summarization.

`CallLog` is not the primary prompt memory. It is the event record. The runtime uses concise slot and phase state for ordinary decisions, while `CallLog` preserves the fuller story.

**What belongs here:**

- User and assistant utterances.
- Tool calls and results.
- Phase transitions.
- Start/end timestamps.
- Handoff summary and detailed exported log.

Example call log shape:

```json
{
  "call_id": "call_abc123",
  "started_at": "2026-05-02T10:00:00Z",
  "ended_at": "2026-05-02T10:08:00Z",
  "transcript": [
    {
      "role": "assistant",
      "text": "故障窓口に切り替わりました。手配確認のためお客様番号をお願いします。"
    },
    {
      "role": "user",
      "text": "12345678です"
    },
    {
      "role": "assistant",
      "text": "本人確認できました、山田太郎様です。"
    }
  ],
  "tool_calls": [
    {
      "tool": "verify_identity",
      "arguments": {
        "customer_id": "12345678"
      },
      "result": {
        "verified": true,
        "customer_id": "12345678"
      }
    }
  ],
  "phase_transitions": [
    {
      "from": null,
      "to": "identity",
      "trigger": "handoff_init"
    }
  ]
}
```

### Layer 6: MAF Skill Task Context

**Purpose:** Execute one business task according to file-based Agent Skill instructions.

The current implementation uses a single faultdesk MAF agent with:

- `SkillsProvider(skill_paths=SKILLS_CATALOG_PATH)` enabled by default.
- File-based skills in `services/faultdesk/app/skills/catalog/*/SKILL.md`.
- Backend Python tools for system actions and slot updates.
- A fresh MAF `AgentSession` for each skill task.

This means MAF context is intentionally short-lived. It is not used as the long-term conversation memory.

**Why fresh sessions are used:**

Full faultdesk runs with `SkillsProvider` and a reused stored `AgentSession` can produce Foundry Responses API `400 Bad Request: Invalid HTTP request received`. Revalidating showed that `SkillsProvider` itself works when each skill task uses a fresh session. Therefore:

- Keep dynamic skill loading enabled.
- Avoid reused MAF sessions for full faultdesk skill-task calls.
- Keep durable call state in `SlotStore`, `PhaseState`, `CallLog`, and Voice Live.

**Current task flow:**

```text
Voice Live tool call: verify_identity(customer_id="12345678")
  -> Orchestrator builds a task prompt
  -> MAF fresh AgentSession starts
  -> SkillsProvider advertises available skills
  -> Model calls load_skill("identity-verification")
  -> Model follows the SKILL.md procedure
  -> Model calls backend verify_identity tool
  -> Backend tool updates SlotStore and CallLog
  -> MAF returns one short customer-facing sentence
  -> Voice Live continues the spoken conversation
```

Example MAF task prompt:

```text
現在の通話ID: call_abc123
現在のオーケストレータ指示:
現在フェーズ: identity
確定済み情報: interview.fault_symptom=インターネットがつながらない

実行タスク:
本人確認フェーズです。identity-verification skill を load_skill で読み、手順に従い、必要なら verify_identity backend tool を実行してください。
入力: customer_id=12345678, name=None, address=None.
tool結果を踏まえ、お客様への次の一言だけを返してください。
```

Example backend tool result:

```json
{
  "verified": true,
  "customer_id": "12345678",
  "verification_method": "customer_id",
  "customer_record": {
    "customer_id": "12345678",
    "name": "山田太郎",
    "address": "東京都渋谷区渋谷1-1-1",
    "phone": "03-1234-5678"
  }
}
```

Example customer-facing MAF output:

```text
本人確認できました、山田太郎様です。
```

### Layer 7: Backend Tool And Adapter Logs

**Purpose:** Keep integration details separate from conversational context.

Backend tools call adapters for systems such as SF113, CULTAS, and AI Search. Their raw or structured results may be logged for debugging, but should not be injected into Voice Live conversation history.

**What can flow back to the caller:**

- A short explanation of the outcome.
- A confirmed fact stored in `SlotStore`.
- A next question or next action.

**What should not flow back directly:**

- Raw API JSON.
- Internal confidence scores.
- Candidate lists unless intentionally converted into a safe user-facing question.
- Backend trace details.

## End-To-End Example

### 1. Frontdesk Triage

User says:

```text
インターネットがつながらないです。
```

Frontdesk routes to faultdesk with:

```json
{
  "call_id": "call_abc123",
  "triage_summary": "インターネットがつながらない",
  "caller_attrs": {},
  "source_phase": "triage"
}
```

### 2. Faultdesk Initialization

Faultdesk creates:

```json
{
  "phase_state": {
    "current": "identity"
  },
  "slot_store": {
    "intake": {
      "greeting_done": true,
      "understood_intent": true
    },
    "interview": {
      "fault_symptom": "インターネットがつながらない"
    }
  }
}
```

Initial assistant behavior:

```text
故障窓口に切り替わりました。手配確認のためお客様番号をお願いします。
```

### 3. Identity Verification

User says:

```text
12345678です。
```

Voice Live calls:

```json
{
  "tool_name": "verify_identity",
  "arguments": {
    "customer_id": "12345678"
  }
}
```

MAF dynamically loads `identity-verification` and calls the backend tool. The backend tool updates slots:

```json
{
  "identity": {
    "customer_id": "12345678",
    "name_match": true,
    "address_match": true,
    "contact_phone": "03-1234-5678",
    "verification_status": "verified"
  }
}
```

Customer-facing response:

```text
本人確認できました、山田太郎様です。
```

### 4. Fault Interview Continues With Durable State

The next MAF task also uses a fresh session, but it receives the current state from `SlotStore` and `PhaseState`:

```json
{
  "current_phase": "interview",
  "filled_slots": {
    "identity": {
      "customer_id": "12345678",
      "verification_status": "verified"
    },
    "interview": {
      "fault_symptom": "インターネットがつながらない"
    }
  }
}
```

So it can ask the next missing question without relying on MAF session memory:

```text
インターネットにつながらない状況ですね。いつ頃から発生していますか？
```

## Current Implementation Files

- `services/frontdesk/app/main.py` - Frontdesk Voice Live session, triage tool handling, and handoff start.
- `services/frontdesk/app/handoff/manager.py` - Service-to-service WebSocket bridge.
- `services/faultdesk/app/main.py` - Faultdesk handoff receiver, Voice Live session, phase/slot initialization, event loop.
- `services/faultdesk/app/orchestrator/instructions.py` - Dynamic instructions generated from phase, slots, and handoff summary.
- `services/faultdesk/app/orchestrator/tools.py` - Voice Live tools that dispatch MAF skill tasks.
- `services/faultdesk/app/skills/agent.py` - Single MAF agent, `SkillsProvider`, fresh per-task sessions, task-local runtime context.
- `services/faultdesk/app/skills/tools.py` - Backend MAF tools that update `SlotStore` and `CallLog`.
- `services/faultdesk/app/skills/catalog/*/SKILL.md` - File-based Agent Skills loaded dynamically with `load_skill`.
- `services/faultdesk/app/slots/store.py` - Per-call structured business facts.
- `services/faultdesk/app/orchestrator/phase_state.py` - Current phase and transition history.
- `services/faultdesk/app/context/call_log.py` - Utterance, tool-call, phase transition, and call-end export record.
- `services/faultdesk/app/context/thread_store.py` - Stored MAF sessions for explicit reuse cases. Not used by the active faultdesk skill-task path.

## Deferred Work

The following ideas are useful but are not the current implementation contract:

- Context-window summarization for long Voice Live calls.
- Structured handoff `context` with recent turns and triage slots.
- Seeding more faultdesk slots from `caller_attrs` and structured triage context.
- Replaying selected previous conversation items into the new desk Voice Live session.
- Persisting call logs to Azure Blob Storage or a queryable database.
- Reintroducing reused MAF sessions only if Foundry + `SkillsProvider` full-path behavior is proven stable.

## Best Practices

1. Keep durable business state structured in `SlotStore` instead of transcript prose.
2. Treat Voice Live context as conversational memory, not as the source of business truth.
3. Keep `SkillsProvider` enabled so file-based skills are dynamically loaded.
4. Use fresh MAF sessions for faultdesk skill tasks until reused sessions are revalidated end to end.
5. Log raw backend details separately and convert them into concise, safe customer-facing replies.
6. Include only the current phase, filled slots, pending slots, and handoff summary in recurring instructions.
7. Use `call_id` as the correlation key across Voice Live events, MAF tasks, backend tools, and exported logs.
