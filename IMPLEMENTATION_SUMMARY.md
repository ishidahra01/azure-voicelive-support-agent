# Azure Voice Live Support Agent - Implementation Summary

## Project Status

This repository contains a comprehensive implementation plan and architecture for an Azure Voice Live-based support agent system with intelligent call routing, phase-based conversation management, and skill-based business logic.

## What's Been Implemented

### ✅ Phase 1: Foundation & Configuration
- Monorepo structure with uv workspace
- Root `pyproject.toml` with workspace configuration
- `.gitignore` for Python, Node.js, and Azure artifacts
- Directory structure for all components

### ✅ Phase 2: Shared Components (`packages/voiceshared`)
**Complete implementation** of shared utilities:
- **Voice Live SDK Wrappers** (`voicelive/session.py`): High-level abstraction for Voice Live sessions
- **Tool Registry** (`tools/registry.py`): Decorator-based tool registration system for function calling
- **WebSocket Protocols** (`ws_protocol/`):
  - `frontend.py`: Browser ↔ Backend message types
  - `handoff.py`: Frontdesk ↔ Desk service message types
- **OOB Client** (`oob/client.py`): Azure OpenAI/Foundry wrapper for non-real-time inference

### ✅ Phase 3: Documentation
**Comprehensive documentation** covering all aspects:
- **`architecture.md`**: System overview, components, data flow, tech stack
- **`handoff-protocol.md`**: Detailed WebSocket handoff specification with message schemas
- **`phase-and-slot-design.md`**: Phase + Slot conversation management pattern
- **`skills-catalog.md`**: Complete catalog of all 7 skills with I/O contracts
- **`context-strategy.md`**: Multi-layer context management strategy (6 layers)
- **ADRs** (Architecture Decision Records):
  - ADR-0001: Monorepo structure
  - ADR-0002: WebSocket bridge for handoff
  - ADR-0003: Microsoft Agent Framework for skills
  - ADR-0004: Phase + Slot conversation model

## Architecture Highlights

### Multi-Service Architecture
```
Browser → Frontdesk (Triage) → Faultdesk (Specialized handling)
  ↓           ↓                      ↓
Audio     Routing              Phase + Slot + Skills
```

### Key Design Patterns

1. **Phase + Slot Conversation Management**
   - 5 phases: intake → identity → interview → visit → closing
   - Flexible navigation with `jump_to_phase()`
   - Persistent slots across phase transitions
   - Dynamic instructions injection

2. **Skill-Based Business Logic**
   - Microsoft Agent Framework file-based Agent Skills
   - Skill instructions maintained in `services/faultdesk/app/skills/catalog/*/SKILL.md`
   - One faultdesk MAF Agent discovers skills with `SkillsProvider(skill_paths=...)`
   - Backend Python tools in `services/faultdesk/app/skills/tools.py` update SlotStore and CallLog in-process
   - No audio I/O in skills (text-only, invoked via orchestrator tools)

3. **Seamless Service Handoff**
   - WebSocket bridge maintains browser connection
   - Audio stream relay (Browser ↔ Frontdesk ↔ Faultdesk)
   - Context transfer via `handoff_init` message
   - Transparent to end user

4. **Multi-Layer Context Management**
   - L1: Voice Live conversation history (with summarization)
   - L2: SlotStore (injected into instructions)
   - L3: Skill AgentThreads (isolated)
   - L4: Business API logs (audit trail)
   - L5: Phase transition history (UI/analytics)
   - L6: Call logs (JSON export)

## Skills Catalog

- **identity-verification**: customer verification with `verify_identity` and `get_current_context`.
- **fault-interview**: fault diagnosis and follow-up questions with `diagnose_fault` and `search_interview_knowledge`.
- **line-test**: remote line testing with `run_line_test`.
- **visit-scheduling**: visit slot proposal and confirmation with `propose_visit_slots` and `confirm_visit`.
- **history-recording**: interaction summarization and persistence with `summarize_call` and `record_history`.

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn
- **Voice**: Azure Voice Live API (`azure-ai-voicelive`)
- **Agent**: Microsoft Agent Framework (Python)
- **Voice model**: Azure Voice Live (`gpt-realtime` by default)
- **Text/OOB model**: Azure OpenAI / Foundry (`gpt-4o` by default)
- **Voice**: ja-JP-NanamiNeural
- **Frontend**: React 18, TypeScript, Vite, Web Audio API (AudioWorklet)
- **Config**: pydantic-settings
- **Auth**: Azure Entra ID (DefaultAzureCredential)
- **Testing**: pytest, pytest-asyncio, httpx
- **Package Manager**: uv

## Next Implementation Steps

### Phase 4: Services (To Be Implemented)

#### Frontdesk Service
Files to create:
```
services/frontdesk/
├── pyproject.toml
├── .env.example
└── app/
    ├── main.py                    # FastAPI + /ws/voice endpoint
    ├── config.py                  # Pydantic settings
    ├── triage/
    │   ├── instructions.py        # Triage agent prompt
    │   └── tools.py               # route_to_fault_desk, etc.
    └── handoff/
        ├── manager.py             # Handoff orchestration
        ├── registry.py            # Desk endpoint registry
        └── bridge.py              # Audio stream bridge
```

Key responsibilities:
- Accept WebSocket from browser (`/ws/voice`)
- Create Voice Live session for triage
- Natural greeting + intent gathering
- Route to appropriate desk via tools
- Bridge audio between browser and desk

#### Faultdesk Service
Files to create:
```
services/faultdesk/
├── pyproject.toml
├── .env.example
└── app/
    ├── main.py                    # FastAPI + /ws/desk endpoint
    ├── config.py
    ├── handoff/
    │   └── inbound.py             # Accept handoff_init
    ├── orchestrator/
    │   ├── conversation.py        # Voice Live orchestrator
    │   ├── instructions.py        # Dynamic instructions
    │   ├── tools.py               # Skill invocation tools
    │   └── phase_state.py         # Phase state management
    ├── phases/
    │   ├── definitions.py         # Phase schemas
    │   └── transitions.py         # Transition rules
    ├── slots/
    │   ├── schema.py              # Slot definitions
    │   └── store.py               # SlotStore implementation
    ├── skills/
    │   ├── base.py                # BaseSkill class
    │   ├── identity.py            # IdentitySkill
    │   ├── interview.py           # InterviewSkill
    │   ├── line_test.py           # LineTestSkill
    │   ├── visit_schedule.py      # VisitScheduleSkill
    │   ├── visit_confirm.py       # VisitConfirmSkill
    │   ├── history.py             # HistorySkill
    │   └── summarizer.py          # SummarizerSkill
    ├── adapters/
    │   ├── sf113.py               # Mock 113SF adapter
    │   ├── cultas.py              # Mock CULTAS adapter
    │   └── ai_search.py           # Mock AI Search adapter
    └── context/
        ├── thread_store.py        # AgentThread management
        └── call_log.py            # Call log & JSON export
```

Key responsibilities:
- Accept WebSocket handoff from frontdesk (`/ws/desk`)
- Create Voice Live session for fault handling
- Manage Phase + Slot state
- Execute skills via tools
- Maintain multi-layer context
- Export call logs at end

### Phase 5: Frontend (To Be Implemented)

```
frontend/
├── package.json
├── vite.config.ts
├── index.html
└── src/
    ├── App.tsx
    ├── hooks/
    │   ├── useAudioWorklet.ts     # AudioWorklet recording/playback
    │   └── useWebSocket.ts        # WebSocket connection
    ├── components/
    │   ├── PhaseBadge.tsx         # Phase progress indicator
    │   ├── SlotChecklist.tsx      # Slot status checklist
    │   ├── HandoffIndicator.tsx   # Handoff status display
    │   ├── TranscriptLog.tsx      # Conversation transcript
    │   └── ToolCallLog.tsx        # Tool execution log
    └── audio/
        ├── worklet.ts             # AudioWorklet processor
        └── encoder.ts             # PCM16 encoding
```

Key features:
- AudioWorklet for low-latency recording (PCM16, 24kHz, mono)
- WebSocket connection to frontdesk `/ws/voice`
- Real-time transcript display
- Phase badge showing current phase
- Slot checklist showing progress
- Handoff indicator during service transitions

### Phase 6: Tooling & Infrastructure

```
tools/
└── run-local.ps1                  # Start all services in parallel

infra/
├── main.bicep                     # Azure infrastructure
├── modules/
│   ├── voice-live.bicep
│   ├── app-service.bicep
│   └── storage.bicep
└── README.md
```

## Running the System (Future)

```powershell
# 1. Set environment variables
cp services/frontdesk/.env.example services/frontdesk/.env
cp services/faultdesk/.env.example services/faultdesk/.env
# Edit .env files with Azure credentials

# 2. Install dependencies
uv sync
cd frontend && npm install

# 3. Start all services
.\tools\run-local.ps1

# Or manually:
# Terminal 1: cd services/faultdesk && uv run uvicorn app.main:app --port 8001
# Terminal 2: cd services/frontdesk && uv run uvicorn app.main:app --port 8000
# Terminal 3: cd frontend && npm run dev
```

## Test Scenarios (Future)

### Scenario 1: Straight Path
```
1. Browser connects to frontdesk
2. User: "インターネットが繋がらない"
3. Frontdesk routes to faultdesk
4. Phases: intake → identity → interview → visit → closing
5. All required slots filled linearly
6. Visit scheduled, call ends
```

### Scenario 2: Back-and-Forth
```
1. Same start as Scenario 1
2. During interview, user: "実は住所が変わったんです"
3. Agent: jump_to_phase("identity")
4. Update address, verify again
5. Agent: jump_to_phase("interview")
6. Resume interview with existing slots intact
7. Continue to visit → closing
```

## Environment Variables

### Frontdesk Service
```bash
VOICE_LIVE_ENDPOINT=https://<region>.api.cognitive.microsoft.com/voice
VOICE_LIVE_API_KEY=<key>
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
FAULT_DESK_WS_URL=ws://localhost:8001/ws/desk
LOG_LEVEL=INFO
```

### Faultdesk Service
```bash
VOICE_LIVE_ENDPOINT=https://<region>.api.cognitive.microsoft.com/voice
VOICE_LIVE_API_KEY=<key>
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
SF113_API_URL=<mock or real>
CULTAS_API_URL=<mock or real>
AI_SEARCH_ENDPOINT=<endpoint>
AI_SEARCH_API_KEY=<key>
LOG_LEVEL=INFO
```

## Acceptance Criteria

- [ ] Two manual E2E scenarios work locally (straight path + back-and-forth)
- [ ] Frontend displays Phase Badge + Slot Checklist + Handoff Indicator
- [ ] Call logs output as JSON per call_id (frontdesk + faultdesk integrated)
- [ ] Unit tests pass: SlotStore, PhaseState, Skills, Handoff protocol
- [ ] Complete documentation in `docs/` ✅
- [ ] README with environment variables and quick start guide ✅

## Key Files

- `README.md` - Project overview and quick start
- `docs/architecture.md` - System architecture
- `docs/handoff-protocol.md` - Handoff specification
- `docs/phase-and-slot-design.md` - Conversation management
- `docs/skills-catalog.md` - Skills reference
- `docs/context-strategy.md` - Context management
- `docs/adr/` - Architecture decisions
- `packages/voiceshared/` - Shared components ✅

## Contributing

This is a sample/reference implementation demonstrating best practices for building production-ready voice agents with Azure Voice Live. Feel free to:

- Use as a starting point for your own implementations
- Adapt patterns to your specific use cases
- Contribute improvements via pull requests
- Report issues or ask questions via GitHub Issues

## License

MIT License - see LICENSE file for details.

## Resources

- [Azure Voice Live API Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/realtime-audio-quickstart)
- [Microsoft Agent Framework](https://learn.microsoft.com/en-us/azure/ai-studio/agents/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)

---

**Note**: This implementation provides a comprehensive architecture and design. The services (frontdesk, faultdesk) and frontend are designed but need to be fully implemented following the patterns and structures defined in the documentation and shared packages.
