# Tests

This directory contains tests for the Azure Voice Live Support Agent.

## Test Structure

```
tests/
├── unit/               # Unit tests for individual components
│   ├── test_slots.py
│   ├── test_phases.py
│   ├── test_skills.py
│   └── test_tools.py
├── integration/        # Integration tests across components
│   ├── test_handoff.py
│   ├── test_phase_transitions.py
│   └── test_skill_integration.py
└── e2e/               # End-to-end tests
    └── test_full_call.py
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test suite
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/

# Run with coverage
uv run pytest --cov=services --cov=packages --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_slots.py

# Run specific test
uv run pytest tests/unit/test_slots.py::test_slot_store_basic
```

## Test Scenarios

### Unit Tests
- Slot validation and storage
- Phase state transitions
- Tool registration and execution
- Message serialization/deserialization
- Skill input/output parsing

### Integration Tests
- Handoff protocol flow
- Phase jumping with slot persistence
- Skill execution with SlotStore updates
- WebSocket message routing

### E2E Tests
- **Straight Path**: intake → identity → interview → visit → closing
- **Back-and-Forth**: Jump from interview to identity, return to interview
- **Validation Errors**: Invalid customer ID, retry logic
- **Handoff Failure**: Desk unavailable, fallback to operator

## Test Fixtures

Common fixtures defined in `conftest.py`:

```python
@pytest.fixture
async def voice_session():
    """Mock Voice Live session"""
    pass

@pytest.fixture
def slot_store():
    """Fresh SlotStore instance"""
    pass

@pytest.fixture
def phase_state():
    """Fresh PhaseState instance"""
    pass

@pytest.fixture
async def mock_sf113():
    """Mock 113SF adapter"""
    pass
```

## Mocking External Services

All external services are mocked for testing:
- Voice Live API: Mock session with synthetic audio
- 113SF: Mock customer database
- CULTAS: Mock diagnosis and dispatch system
- AI Search: Mock knowledge base responses

## Test Data

Test data located in `tests/fixtures/`:
- `customers.json`: Mock customer records
- `visit_slots.json`: Mock available time slots
- `audio_samples/`: Small PCM16 audio samples for testing

## CI/CD Integration

Tests run automatically in GitHub Actions:
- On push to any branch
- On pull request
- Nightly full test suite with E2E scenarios

## Writing New Tests

### Unit Test Example

```python
@pytest.mark.asyncio
async def test_slot_store_basic():
    store = SlotStore(call_id="test_001")
    store.set("identity", "customer_id", "12345678")

    assert store.get("identity", "customer_id") == "12345678"
    assert store.is_filled("identity", "customer_id") == True
```

### Integration Test Example

```python
@pytest.mark.asyncio
async def test_handoff_protocol():
    # Start frontdesk session
    frontdesk = await create_frontdesk_session()

    # Trigger handoff
    await frontdesk.execute_tool("route_to_fault_desk", {
        "summary": "Internet outage",
        "caller_attrs": {"phone": "03-1234-5678"}
    })

    # Verify handoff initiated
    assert frontdesk.handoff_status == "connected"
```

## Best Practices

1. **Isolate Tests**: Each test should be independent
2. **Use Fixtures**: Share setup code via fixtures
3. **Mock External Calls**: Never call real APIs in tests
4. **Assert Specifically**: Check specific values, not just truthiness
5. **Test Edge Cases**: Invalid inputs, timeouts, errors
6. **Keep Tests Fast**: Unit tests should run in milliseconds

## Debugging Tests

```bash
# Run with verbose output
uv run pytest -v

# Run with print statements
uv run pytest -s

# Run with debugger on failure
uv run pytest --pdb

# Run only failed tests from last run
uv run pytest --lf
```
