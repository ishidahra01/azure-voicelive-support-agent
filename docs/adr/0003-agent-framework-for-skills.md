# ADR 0003: Microsoft Agent Framework for Skills

## Status
Accepted

## Context
The faultdesk service needs to handle complex business logic such as identity verification, fault diagnosis, visit scheduling, etc. We need to decide how to structure this logic.

Options considered:
1. **Direct LLM Calls**: Each business function makes direct OpenAI API calls
2. **Single Monolithic Agent**: One large agent with all business logic
3. **Microsoft Agent Framework Skills**: Independent ChatAgents for each business domain
4. **Custom Agent Framework**: Build our own agent abstraction

## Decision
We use **Microsoft Agent Framework** to implement independent skills (ChatAgents) for each business domain, invoked as tools by the Voice Live orchestrator.

## Rationale

### Why Microsoft Agent Framework:

1. **Built for Azure**: Native integration with Azure OpenAI and other Azure services
2. **AgentThread Management**: Built-in context management per agent thread
3. **Tool Support**: First-class support for function calling
4. **Production Ready**: Battle-tested framework from Microsoft
5. **Python Support**: Full Python SDK with async support
6. **Ecosystem**: Growing ecosystem of pre-built agents and tools

### Architecture:

```
Voice Live Orchestrator (Single Voice Agent)
    │
    ├─ Tool: verify_identity() ──────> IdentitySkill (ChatAgent)
    │                                    ├─ AgentThread (isolated context)
    │                                    ├─ Tools: sf113_get_customer, ...
    │                                    └─ Return: {structured, conversational}
    │
    ├─ Tool: interview_fault() ──────> InterviewSkill (ChatAgent)
    │                                    ├─ AgentThread (isolated context)
    │                                    ├─ Tools: cultas_diagnose, ...
    │                                    └─ Return: {structured, conversational}
    │
    └─ Tool: propose_visit_slots() ──> VisitScheduleSkill (ChatAgent)
                                        ├─ AgentThread (isolated context)
                                        ├─ Tools: sf113_get_visit_slots, ...
                                        └─ Return: {structured, conversational}
```

### Key Benefits:

**1. Context Isolation**
Each skill maintains its own AgentThread, preventing context pollution:
```python
# Each skill gets its own isolated context
identity_thread = AgentThread.get_or_create(f"{call_id}:identity")
interview_thread = AgentThread.get_or_create(f"{call_id}:interview")
```

**2. Specialized Prompts**
Each skill has a focused system prompt:
```python
class IdentitySkill(ChatAgent):
    system_prompt = """
    You are an identity verification specialist.
    Your sole focus is verifying customer identity using available tools.
    Be thorough but efficient. Guide customers if they don't have required information.
    """
```

**3. Skill-Specific Tools**
Each skill has its own set of tools:
```python
identity_skill = ChatAgent(
    system_prompt=identity_prompt,
    tools=[sf113_get_customer, sf113_fuzzy_match_name, sf113_verify_address]
)

interview_skill = ChatAgent(
    system_prompt=interview_prompt,
    tools=[cultas_diagnose, ai_search_interview_kb, cultas_get_device_info]
)
```

**4. Reusable and Testable**
Skills can be tested independently:
```python
def test_identity_skill():
    skill = IdentitySkill(call_id="test_001")
    result = await skill.execute({"customer_id": "12345678"})
    assert result["structured"]["verified"] == True
```

**5. No Audio I/O in Skills**
Skills are text-only, keeping them simple and focused:
- Voice Live orchestrator handles all audio
- Skills receive text parameters, return text results
- Skills can be used in non-voice contexts (chat, API)

## Consequences

### Positive:
- **Clean Separation**: Business logic separated from conversation management
- **Testability**: Each skill can be unit tested independently
- **Maintainability**: Skills can be updated without affecting others
- **Reusability**: Skills can be used across different orchestrators
- **Parallel Development**: Different teams can work on different skills
- **Framework Benefits**: Leverage Microsoft's AgentThread, tool management, etc.

### Negative:
- **Dependency**: Tied to Microsoft Agent Framework ecosystem
- **Learning Curve**: Team must learn Agent Framework concepts
- **Abstraction Overhead**: Extra layer between Voice Live and business logic
- **Version Lock-in**: Must keep Agent Framework version compatible

### Mitigations:

**Dependency Risk**:
- Agent Framework is well-supported by Microsoft
- Open-source, can fork if needed
- Skills use standard OpenAI SDK underneath, could migrate if necessary

**Learning Curve**:
- Framework is intuitive for developers familiar with ChatGPT API
- Good documentation and examples available
- Skills are simple Python classes

## Implementation Pattern

### Skill Base Class

```python
from microsoft_agent_framework import ChatAgent, AgentThread

class BaseSkill:
    def __init__(self, call_id: str, skill_name: str):
        self.call_id = call_id
        self.skill_name = skill_name
        self.thread = AgentThread.get_or_create(f"{call_id}:{skill_name}")

    async def execute(self, params: dict) -> dict:
        """
        Execute the skill and return structured + conversational results.

        Returns:
            {
                "structured": {...},      # For SlotStore
                "conversational": "..."   # For Voice Live
            }
        """
        raise NotImplementedError
```

### Skill Implementation

```python
class IdentitySkill(BaseSkill, ChatAgent):
    def __init__(self, call_id: str):
        BaseSkill.__init__(self, call_id, "identity")
        ChatAgent.__init__(
            self,
            system_prompt=self._get_system_prompt(),
            tools=self._get_tools(),
            thread=self.thread
        )

    def _get_system_prompt(self) -> str:
        return """You are an identity verification specialist..."""

    def _get_tools(self) -> list:
        return [sf113_get_customer, sf113_fuzzy_match_name]

    async def execute(self, params: dict) -> dict:
        # Build input message
        message = self._format_input(params)

        # Get response from Agent
        response = await self.complete(message)

        # Parse response
        return {
            "structured": self._extract_structured(response),
            "conversational": self._extract_conversational(response)
        }
```

### Orchestrator Integration

```python
@register_tool(description="Verify customer identity")
async def verify_identity(customer_id: str = None, name: str = None):
    skill = get_skill("identity", call_id=current_call_id())

    result = await skill.execute({
        "customer_id": customer_id,
        "name": name
    })

    # Update SlotStore
    update_slots("identity", result["structured"])

    # Return conversational text to Voice Live
    return result["conversational"]
```

## Alternatives Considered

### 1. Direct LLM Calls
**Rejected because**:
- No context management (would need to build our own)
- No agent thread isolation
- No built-in tool support
- Reinventing the wheel

### 2. Single Monolithic Agent
**Rejected because**:
- Context pollution (all business logic in one context)
- Hard to test specific functionality
- Prompts become unwieldy
- Difficult to maintain as system grows

### 3. Custom Agent Framework
**Rejected because**:
- Significant development effort
- Would replicate existing solutions
- Maintenance burden
- Not the focus of this project

## Testing Strategy

### Unit Tests
```python
@pytest.mark.asyncio
async def test_identity_skill_success():
    skill = IdentitySkill(call_id="test_001")
    result = await skill.execute({"customer_id": "12345678"})

    assert result["structured"]["verified"] == True
    assert result["structured"]["customer_record"]["customer_id"] == "12345678"
    assert "山田太郎" in result["conversational"]
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_identity_flow():
    # Test orchestrator → skill → slot update
    orchestrator = create_test_orchestrator()
    await orchestrator.process_tool_call("verify_identity", {"customer_id": "12345678"})

    # Verify slot updated
    assert slot_store.get("identity", "customer_id") == "12345678"
    assert slot_store.get("identity", "verification_status") == "verified"
```

## Dependencies

```toml
[dependencies]
microsoft-agent-framework = ">=0.1.0"  # Exact version TBD based on availability
azure-ai-inference = ">=1.0.0"
openai = ">=1.58.0"
```

## Migration Path

If we need to migrate away from Agent Framework:
1. Skills use standard OpenAI SDK underneath
2. Can replace Agent Framework with direct SDK calls
3. AgentThread replaced with custom context management
4. Skill interface remains the same (execute method)

## References
- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/en-us/azure/ai-studio/agents/)
- [Azure AI Agent Service](https://learn.microsoft.com/en-us/azure/ai-services/agents/)
- [OpenAI Assistants API](https://platform.openai.com/docs/assistants/overview) (similar concepts)
