# Skills Catalog

## Overview

Faultdesk skills use the Microsoft Agent Framework file-based Agent Skills pattern. Skill instructions are discovered from `SKILL.md` files in filesystem directories, while backend actions stay in Python so they can update the active `SlotStore`, `CallLog`, and phase context in-process.

Each skill:

- Lives under `services/faultdesk/app/skills/catalog/<skill-name>/SKILL.md`
- Defines its purpose, usage rules, and references in Markdown
- Is discovered by one faultdesk MAF `Agent` through `SkillsProvider(skill_paths=...)`
- Uses backend tools from `services/faultdesk/app/skills/tools.py`
- Has no direct audio I/O; Voice Live reaches it through orchestrator tools

## Runtime Architecture

```text
Voice Live orchestrator tool
        |
        v
services/faultdesk/app/orchestrator/tools.py
        |
        v
run_faultdesk_agent(...)
        |
        v
FaultdeskSkillsAgent
  - SkillsProvider(skill_paths=services/faultdesk/app/skills/catalog)
  - backend tools from services/faultdesk/app/skills/tools.py
        |
        v
catalog/<skill-name>/SKILL.md + references/*
```

Each backend skill task creates a fresh MAF `AgentSession`. Runtime objects are passed to backend tools through a task-local context so tools can mutate the current `SlotStore` and append call log entries without creating a separate IPC layer. Durable call context remains in Voice Live, `PhaseState`, `SlotStore`, and `CallLog`, not in the MAF session.

## Directory Structure

```text
services/faultdesk/app/skills/
├── __init__.py
├── agent.py                 # Builds the single skill-enabled MAF Agent
├── tools.py                 # Backend tools for SF113, CULTAS, AI Search, SlotStore, CallLog
└── catalog/
    ├── identity-verification/
    │   ├── SKILL.md
    │   └── references/
    │       └── slot-contract.md
    ├── fault-interview/
    │   ├── SKILL.md
    │   └── references/
    │       └── interview-playbook.md
    ├── line-test/
    │   └── SKILL.md
    ├── visit-scheduling/
    │   ├── SKILL.md
    │   └── references/
    │       └── dispatch-faq.md
    └── history-recording/
        └── SKILL.md
```

## Skill List

- `identity-verification`: verifies caller identity from customer ID, name, address, or contact details. Backend tools: `get_current_context`, `verify_identity`.
- `fault-interview`: diagnoses symptoms and asks focused follow-up questions. Backend tools: `get_current_context`, `diagnose_fault`, `search_interview_knowledge`.
- `line-test`: runs remote line tests and interprets results. Backend tools: `get_current_context`, `run_line_test`.
- `visit-scheduling`: proposes and confirms technician visit slots. Backend tools: `get_current_context`, `propose_visit_slots`, `confirm_visit`.
- `history-recording`: summarizes and persists the call record. Backend tools: `get_current_context`, `summarize_call`, `record_history`.

## Invocation Pattern

Voice Live calls a normal orchestrator tool, such as `verify_identity`. The orchestrator tool delegates to the single MAF skill agent with a task-specific prompt. The skill agent loads the relevant file-based skill instructions, invokes backend tools, and returns one short customer-facing Japanese response.

```python
async def verify_identity(customer_id: str | None = None, name: str | None = None, address: str | None = None) -> str:
    return await run_faultdesk_agent(
        call_id=get_current_call_id(),
        task=(
            "本人確認フェーズです。identity-verification skill を使い、"
            f"入力: customer_id={customer_id}, name={name}, address={address}."
        ),
        slot_store=get_current_slot_store(),
        phase_state=get_current_phase_state(),
        call_log=get_current_call_log(),
    )
```

## Adding a Skill

1. Create `services/faultdesk/app/skills/catalog/<new-skill>/SKILL.md`.
2. Add frontmatter with `name`, `description`, `license`, `compatibility`, and `metadata`.
3. Put caller-facing rules, procedure, tool usage guidance, and escalation rules in Markdown.
4. Add reference files under `references/` when the skill needs playbooks or contracts.
5. Add any required backend operation to `services/faultdesk/app/skills/tools.py` and include it in `get_faultdesk_tools()`.
6. Add or update the orchestrator wrapper in `services/faultdesk/app/orchestrator/tools.py` when Voice Live needs a new callable action.

## Testing

Recommended checks after skill edits:

```powershell
.\.venv\Scripts\python.exe -c "from app.skills import get_faultdesk_agent, SKILLS_CATALOG_PATH; print(SKILLS_CATALOG_PATH); print(type(get_faultdesk_agent()).__name__)"
.\.venv\Scripts\python.exe -m compileall services\faultdesk\app\skills services\faultdesk\app\orchestrator
```

For backend tool behavior, invoke the wrapped MAF tool with a task-local runtime context and verify SlotStore updates. This confirms file-based skill instructions and Python backend actions remain cleanly separated.
