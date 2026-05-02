# ADR 0003: Microsoft Agent Framework for Skills

## Status

Accepted

## Context

The faultdesk service needs to handle business logic such as identity verification, fault diagnosis, line testing, visit scheduling, and history recording. The voice conversation itself is owned by Azure Voice Live, but these backend tasks need procedural skill instructions, tool use, and access to the current call state.

The context-management decision in [Context Management Strategy](../context-strategy.md) is important here: MAF sessions are not the long-term memory for a call. Durable business state lives in `PhaseState`, `SlotStore`, handoff context, and `CallLog`.

Options considered:

1. Direct LLM calls from each business function.
2. One monolithic text agent with all procedures embedded in its prompt.
3. Independent hand-written skill classes per business domain.
4. Microsoft Agent Framework with file-based Agent Skills and `SkillsProvider`.

## Decision

Use Microsoft Agent Framework as a text-only skill executor behind Voice Live tools. Faultdesk uses one MAF `Agent` with `SkillsProvider(skill_paths=...)` so file-based skills under `services/faultdesk/app/skills/catalog/*/SKILL.md` are dynamically advertised and loaded with `load_skill` / `read_skill_resource`.

Each Voice Live orchestrator tool delegates to this MAF agent for a single backend task. The task uses a fresh MAF `AgentSession`, loads the relevant skill instructions, calls Python backend tools, updates `SlotStore` / `CallLog`, and returns one short customer-facing Japanese response to Voice Live.

## Architecture

```text
Voice Live Orchestrator
    |
    | tool call: verify_identity / interview_fault / run_line_test / ...
    v
services/faultdesk/app/orchestrator/tools.py
    |
    v
run_faultdesk_agent(...)
    |
    v
FaultdeskSkillsAgent
    - SkillsProvider(skill_paths=services/faultdesk/app/skills/catalog)
    - Fresh AgentSession per task
    - Backend tools from services/faultdesk/app/skills/tools.py
    |
    v
catalog/<skill-name>/SKILL.md + references/*
```

## Context Rules

- Voice Live owns the live spoken conversation and tool-call decisions.
- `PhaseState` owns the workflow phase.
- `SlotStore` owns confirmed business facts.
- `CallLog` owns audit/debug history.
- `handoff_init` and seeded slots transfer context between desks.
- MAF `AgentSession` is short-lived per backend skill task.
- `ThreadStore` exists only for explicit future reuse cases and is not the active faultdesk skill-task memory.

## Rationale

### Dynamic Skill Loading

File-based Agent Skills keep procedural knowledge in `SKILL.md` files instead of hard-coding each skill as a Python class. `SkillsProvider` lets the MAF agent progressively disclose the relevant skill only when the task needs it.

### Clean State Boundary

Backend tools update `SlotStore` and `CallLog` in-process through task-local context. This keeps durable state outside the model session and avoids relying on MAF conversation history as the business source of truth.

### Voice / Text Separation

Voice Live remains responsible for the natural spoken experience. MAF remains text-only and does not directly handle audio I/O.

### Testability

Skills can be checked at two levels: the Markdown skill contract and the Python backend tools. Orchestrator wrappers can be tested by asserting that a tool call updates slots and returns an appropriate customer-facing response.

## Consequences

### Positive

- Skill procedures are easy to inspect and update in Markdown.
- Dynamic loading avoids a permanently oversized prompt.
- Durable state has a clear owner: `PhaseState`, `SlotStore`, and `CallLog`.
- Skills remain reusable outside a voice channel because they are text-only.
- The current design avoids Foundry errors observed with reused full-path MAF sessions.

### Negative

- Developers need to understand both Voice Live tools and MAF file-based skills.
- Tool behavior is split between Markdown procedure and Python backend implementation.
- Fresh MAF sessions mean the task prompt must include enough current durable state for each run.

### Mitigations

- Keep [Context Management Strategy](../context-strategy.md) as the source of truth for context responsibilities.
- Keep [Skills Catalog](../skills-catalog.md) aligned with the actual skill directory layout.
- Require orchestrator task prompts to name the target skill and request `load_skill`.
- Keep backend tools small and deterministic where possible.

## Implementation Pattern

```python
async def verify_identity(customer_id: str | None = None, name: str | None = None, address: str | None = None) -> str:
    return await run_faultdesk_agent(
        call_id=get_current_call_id(),
        task=(
            "本人確認フェーズです。identity-verification skill を load_skill で読み、"
            "必要なら verify_identity backend tool を実行してください。"
            f" 入力: customer_id={customer_id}, name={name}, address={address}."
        ),
        slot_store=get_current_slot_store(),
        phase_state=get_current_phase_state(),
        call_log=get_current_call_log(),
    )
```

The MAF agent is built once per process. Each task creates a fresh session:

```python
agent = get_faultdesk_agent()
session = agent.create_session()
result = await agent.run(prompt, session=session)
```

## Skill Catalog

Current file-based skills:

- `identity-verification`
- `fault-interview`
- `line-test`
- `visit-scheduling`
- `history-recording`

## Testing Strategy

- Compile Python modules after skill or tool changes.
- Exercise orchestrator wrappers such as `verify_identity` with a task-local `SlotStore`, `PhaseState`, and `CallLog`.
- Assert that backend tools update slots rather than relying on MAF session history.
- Smoke test with `MAF_USE_SKILLS_PROVIDER=true` so `load_skill` is used.

## References

- [Context Management Strategy](../context-strategy.md)
- [Skills Catalog](../skills-catalog.md)
- [Azure AI Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/)
