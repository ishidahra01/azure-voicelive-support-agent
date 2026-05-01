# ADR 0004: Phase + Slot Conversation Model

## Status
Accepted

## Context
The faultdesk needs a conversation management strategy that:
1. Ensures all required information is collected (no gaps)
2. Allows natural, flexible conversation flow (not rigid script)
3. Handles users jumping between topics
4. Provides clear progress visibility
5. Supports complex multi-step workflows

Options considered:
1. **State Machine**: Fixed sequence of states with defined transitions
2. **Free-Form LLM**: Let LLM handle everything with just system prompt
3. **Phase + Slot Model**: Phases with required slots, flexible navigation
4. **Dialog Tree**: Branching tree of predefined conversation paths

## Decision
We implement a **Phase + Slot model** where:
- **Phases**: High-level stages (identity, interview, visit, closing)
- **Slots**: Individual pieces of information within each phase
- **Flexible Navigation**: Can jump between phases as needed
- **Persistence**: Slots persist across phase transitions
- **Dynamic Instructions**: Phase and slot state injected into LLM instructions every turn

## Rationale

### The Problem with Pure State Machines:

State machines are too rigid:
```
identity → interview → visit → closing
     ↓          ↓         ↓
   stuck     stuck     stuck

# User: "Actually, my address changed"
# Agent: <stuck in interview phase, can't go back to identity>
```

### The Problem with Free-Form LLM:

No guarantees about information collection:
```
Agent: "Tell me about your internet problem"
User: "It's been down for 3 days"
Agent: "I'll send a technician tomorrow"
# Wait! We never verified identity or collected customer ID!
```

### Phase + Slot Solves Both:

```
Phases: [identity] → [interview] → [visit] → [closing]
           ↕             ↕            ↕           ↕
        jump_to_phase() allows free movement

Slots in each phase:
  identity: [customer_id ✓, name_match ✓, address ✗]
  interview: [symptom ✓, started_at ✗, env ✗]

# User mid-interview: "Actually my address changed"
Agent: <calls jump_to_phase("identity")>
       <updates address_match slot>
       <calls jump_to_phase("interview")>
       <continues with pending interview slots>

# All identity slots still filled, address updated
```

## Architecture

### Phase Definition

```python
class Phase:
    name: str
    slots: List[Slot]
    entry_hook: Optional[Callable]
    exit_hook: Optional[Callable]

PHASES = {
    "intake": Phase(
        name="intake",
        slots=[
            Slot("greeting_done", required=True, type="bool"),
            Slot("understood_intent", required=True, type="bool")
        ]
    ),
    "identity": Phase(
        name="identity",
        slots=[
            Slot("customer_id", required=True, type="str", validator=is_8digit),
            Slot("name_match", required=True, type="bool"),
            Slot("address_match", required=True, type="bool"),
            Slot("contact_phone", required=True, type="str"),
        ]
    ),
    # ... more phases
}
```

### Slot Definition

```python
class Slot:
    name: str
    required: bool
    type: Type  # str, int, bool, dict, list
    validator: Optional[Callable[[Any], bool]]
    default: Any = None
    description: str = ""
```

### Dynamic Instructions Injection

Every turn, inject current state:

```python
def generate_instructions(phase_state, slot_store):
    current_phase = phase_state.current
    pending_slots = slot_store.get_pending_slots(current_phase)
    filled_slots = slot_store.get_all_filled_slots()

    return f"""
    You are a fault desk agent.

    【Current Phase】 {current_phase}

    【Pending Information in This Phase】
    {format_pending(pending_slots)}

    【All Confirmed Information】
    {format_filled(filled_slots)}

    【Instructions】
    - Collect pending information through natural questions
    - If user mentions a different topic, use jump_to_phase()
    - When information is confirmed, call appropriate skill tool
    - When all required slots filled, suggest moving to next phase
    """
```

### Phase Navigation

```python
@register_tool(description="Jump to a different conversation phase")
async def jump_to_phase(target_phase: str, reason: str = None):
    phase_state.transition_to(target_phase, trigger=f"manual:{reason}")

    # Update Voice Live instructions with new phase context
    instructions = generate_instructions(phase_state, slot_store)
    await session.update(instructions=instructions)

    # Notify frontend
    send_phase_changed_message(phase_state.previous, target_phase)

    return f"Moved to {target_phase} phase. Continue conversation naturally."
```

## Consequences

### Positive:
- **Completeness Guaranteed**: Required slots must be filled before proceeding
- **Flexibility**: Can jump between phases naturally
- **Progress Visibility**: UI shows filled/pending slots
- **Debuggability**: Clear state at any point in conversation
- **Testability**: Can verify slot filling logic independently
- **Recovery**: If error occurs, can restart from current phase without losing slots

### Negative:
- **Implementation Complexity**: More complex than pure LLM or simple state machine
- **Slot Design Overhead**: Must carefully design slot schema upfront
- **Context Injection**: Need to update instructions every turn (small latency cost)
- **State Management**: Must persist and synchronize phase/slot state

### Trade-offs Accepted:

**Complexity vs Reliability**:
- Accept: Implementation complexity
- Gain: Guaranteed information collection

**Instruction Overhead vs Context**:
- Accept: ~1-2KB of instructions injected per turn
- Gain: LLM always aware of current state

## Implementation Details

### SlotStore

```python
class SlotStore:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.data = {phase: {} for phase in PHASES}

    def set(self, phase: str, slot_name: str, value: Any, status: str = "filled"):
        self.data[phase][slot_name] = {
            "value": value,
            "status": status,
            "updated_at": datetime.utcnow()
        }

    def get(self, phase: str, slot_name: str) -> Any:
        return self.data[phase].get(slot_name, {}).get("value")

    def get_pending_slots(self, phase: str) -> List[Slot]:
        """Get all required slots that are not yet filled in this phase."""
        phase_def = PHASES[phase]
        return [
            slot for slot in phase_def.slots
            if slot.required and not self.is_filled(phase, slot.name)
        ]

    def is_phase_complete(self, phase: str) -> bool:
        """Check if all required slots in phase are filled."""
        return len(self.get_pending_slots(phase)) == 0
```

### PhaseState

```python
class PhaseState:
    def __init__(self, call_id: str, initial_phase: str = "intake"):
        self.call_id = call_id
        self.current = initial_phase
        self.previous = None
        self.history = []

    def transition_to(self, target_phase: str, trigger: str):
        self.previous = self.current
        self.current = target_phase
        self.history.append({
            "from": self.previous,
            "to": target_phase,
            "trigger": trigger,
            "timestamp": datetime.utcnow()
        })

    def can_transition_to(self, target_phase: str) -> bool:
        # In this design, all phases can transition to any other phase
        return target_phase in PHASES
```

## UI Integration

### Phase Badge Component

```typescript
interface PhaseBadgeProps {
  current: string;
  phases: string[];
  completed: string[];
}

// Displays: [✓ intake] [✓ identity] [● interview] [○ visit] [○ closing]
```

### Slot Checklist Component

```typescript
interface SlotChecklistProps {
  phase: string;
  slots: Array<{
    name: string;
    status: 'pending' | 'filled' | 'invalid';
    required: boolean;
    value?: any;
  }>;
}

// Displays:
// Interview Phase
// ☑ fault_symptom: ネット不通
// ☐ fault_started_at (required)
// ☐ indoor_env (required)
```

## Validation

### Automatic Validation

```python
def validate_slot_value(slot: Slot, value: Any) -> Tuple[bool, Optional[str]]:
    # Type check
    if not isinstance(value, slot.type):
        return False, f"Expected {slot.type}, got {type(value)}"

    # Custom validator
    if slot.validator and not slot.validator(value):
        return False, f"Validation failed for {slot.name}"

    return True, None
```

### Validation in Slot Setting

```python
def set_slot(phase: str, slot_name: str, value: Any):
    slot_def = get_slot_definition(phase, slot_name)

    valid, error = validate_slot_value(slot_def, value)

    if valid:
        slot_store.set(phase, slot_name, value, status="filled")
    else:
        slot_store.set(phase, slot_name, value, status="invalid")
        logger.warning(f"Invalid slot value: {error}")
        # Inform agent to ask again
```

## Testing Strategy

### Unit Tests

```python
def test_slot_store():
    store = SlotStore("test_001")
    store.set("identity", "customer_id", "12345678")

    assert store.get("identity", "customer_id") == "12345678"
    assert store.is_filled("identity", "customer_id") == True

def test_phase_transitions():
    state = PhaseState("test_001")
    state.transition_to("identity", trigger="auto")

    assert state.current == "identity"
    assert state.previous == "intake"
    assert len(state.history) == 1
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_phase_jump_preserves_slots():
    # Fill slots in identity phase
    await orchestrator.execute_tool("verify_identity", {"customer_id": "12345678"})

    # Jump to interview
    await orchestrator.execute_tool("jump_to_phase", {"target_phase": "interview"})

    # Jump back to identity
    await orchestrator.execute_tool("jump_to_phase", {"target_phase": "identity"})

    # Verify slots still filled
    assert slot_store.get("identity", "customer_id") == "12345678"
```

## Alternatives Considered

### 1. Pure State Machine
**Rejected because**:
- Too rigid, can't handle user topic changes
- Forces linear conversation flow
- Poor user experience when user needs to backtrack

### 2. Free-Form LLM
**Rejected because**:
- No guarantees about information completeness
- Hard to track progress
- Difficult to recover from errors
- Cannot ensure business requirements met

### 3. Dialog Tree
**Rejected because**:
- Exponential complexity as conversation grows
- Cannot handle unanticipated user responses
- Maintenance nightmare
- Not suitable for LLM-based conversation

## Future Enhancements

1. **Conditional Slots**: Slots that are required only if certain conditions met
2. **Slot Dependencies**: Slot A must be filled before Slot B can be asked
3. **Multi-Value Slots**: Slots that can have multiple values
4. **Slot Confidence**: Track confidence level of filled slots
5. **Automatic Slot Extraction**: Use NLU to extract slots from utterances automatically

## References
- [Task-Oriented Dialogue Systems](https://arxiv.org/abs/2003.07490)
- [Slot Filling in Dialogue Systems](https://aclanthology.org/P19-1546.pdf)
- [Voice User Interface Design](https://www.oreilly.com/library/view/voice-user-interface/9781491955390/)
