# Architecture Overview

## 1. System Goals

### Goals
1. **End-to-End Voice Support Agent**: Demonstrate a complete voice-based support flow from initial triage through task completion
2. **Phase + Slot Conversation Model**: Structured yet flexible conversation management that prevents information gaps while allowing natural dialogue
3. **Seamless Service Handoff**: Transfer calls between services (frontdesk → specialized desks) without disconnecting the customer
4. **Skill-Based Architecture**: Modular business procedures implemented as file-based Microsoft Agent Framework Agent Skills
5. **Extensibility**: Easy to add new desk services (billing, general inquiry, etc.) by implementing the handoff protocol

### Non-Goals (Initial Version)
- PSTN gateway integration (browser-based testing only)
- Production API integration for 113SF/CULTAS/AI Search (mock implementations)
- Production-ready infrastructure deployment (templates only)
- Multiple desk implementations (fault desk only, with interfaces for others)

## 2. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                       Browser (React UI)                           │
│  - AudioWorklet recording (PCM16 24kHz)                            │
│  - Playback / Phase Badge / Slot Checklist UI                      │
└───────────────────────────────┬────────────────────────────────────┘
                                │ WebSocket: /ws/voice
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│  services/frontdesk  (Triage & Routing)                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Voice Live Session (gpt-4o-realtime, ja-JP-NanamiNeural)     │  │
│  │  - Natural greeting + intent gathering only                  │  │
│  │  - Tools:                                                    │  │
│  │      • route_to_fault_desk(summary, caller_attrs)            │  │
│  │      • route_to_billing_desk(...) ← Future                   │  │
│  │      • route_to_general(...) ← Future                        │  │
│  │      • end_call() / escalate_to_human()                      │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
│                               │ Tool execution                      │
│  ┌────────────────────────────▼─────────────────────────────────┐  │
│  │ Handoff Manager / Bridge                                     │  │
│  │  - Connect to faultdesk WebSocket                            │  │
│  │  - Detach old Voice Live session                             │  │
│  │  - Bridge audio: Browser ↔ Faultdesk                         │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
└─────────────────────────────────┼──────────────────────────────────┘
                                 │ WebSocket: /ws/desk
                                 │ Initial: handoff_init {call_id, summary, attrs}
                                 │ Ongoing: audio frames + control events
                                 ▼
┌────────────────────────────────────────────────────────────────────┐
│  services/faultdesk  (Fault Handling Desk Agent)                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Conversation Orchestrator (Voice Live single agent)          │  │
│  │  - Single voice agent for all interactions                   │  │
│  │  - Dynamic instructions injection (Phase + Slot state)       │  │
│  │  - Coarse-grained tools:                                     │  │
│  │      • verify_identity / interview_fault / run_line_test /   │  │
│  │        propose_visit_slots / confirm_visit /                 │  │
│  │        record_history / jump_to_phase /                      │  │
│  │        handoff_to_operator                                   │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
│                               │                                     │
│  ┌────────────────────────────▼─────────────────────────────────┐  │
│  │ Microsoft Agent Framework Skills (Text-based, no audio I/O)  │  │
│  │  - Single MAF agent with SkillsProvider                      │  │
│  │  - File skills loaded from catalog/*/SKILL.md via load_skill  │  │
│  │  - Fresh AgentSession per backend skill task                  │  │
│  │  - Backend tools update SlotStore and CallLog                 │  │
│  └────────────────────────────┬─────────────────────────────────┘  │
│                               │                                     │
│  ┌────────────────────────────▼─────────────────────────────────┐  │
│  │ Adapters (Mock): 113SF / CULTAS / AI Search                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ State: SlotStore + PhaseState + CallLog                      │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

## 3. Design Principles

| Principle | Description |
|-----------|-------------|
| **1. Frontdesk as Gateway** | Frontdesk focuses on natural triage and routing. No complex agent logic—just simple function calling. |
| **2. Single Voice Orchestrator** | Each desk service uses a single Voice Live session to avoid unnatural voice/personality switches. |
| **3. Text-Based Skills** | Business logic implemented as Microsoft Agent Framework file-based Agent Skills. No audio I/O - invoked via tools. |
| **4. Phase + Slot Model** | Each phase defines required slots. Flexible navigation with `jump_to_phase` while maintaining slot persistence. |
| **5. Multi-Layer Context** | Separate contexts: Voice Live conversation, SlotStore/PhaseState business state, CallLog audit history, short-lived MAF skill task context, Business API logs. |
| **6. Stream Handoff** | Handoff replaces Voice Live upstream while keeping browser WebSocket alive. Transparent to end user. |
| **7. Pluggable Desks** | New desk services can be added by implementing the handoff protocol interface. |

## 4. Component Breakdown

### 4.1 Frontend (React + Web Audio)

**Responsibilities:**
- Capture microphone audio via AudioWorklet (PCM16, 24kHz, mono)
- Send audio to backend via WebSocket
- Receive and play audio from backend
- Display Phase Badge, Slot Checklist, Handoff Indicator
- Show transcript log and tool call log

**Key Technologies:**
- React 18 + TypeScript
- Vite for build tooling
- Web Audio API for audio processing
- WebSocket for real-time communication

### 4.2 Frontdesk Service

**Responsibilities:**
- Initial customer greeting and intent gathering
- Route to appropriate desk service
- Manage handoff to backend desks
- Bridge audio streams during handoff

**Key Components:**
- `app/main.py`: FastAPI application with WebSocket endpoint `/ws/voice`
- `app/voicelive/`: Voice Live session management
- `app/triage/`: Triage logic and routing tools
- `app/handoff/`: Handoff manager and bridge logic

**Tools:**
- `route_to_fault_desk(summary, caller_attrs)`
- `route_to_billing_desk(...)`  ← Future
- `route_to_general(...)`  ← Future
- `end_call()`
- `escalate_to_human()`

### 4.3 Faultdesk Service

**Responsibilities:**
- Handle fault/repair inquiries end-to-end
- Manage Phase + Slot conversation state
- Delegate backend work to MAF file-based Agent Skills
- Maintain multi-layer context

**Key Components:**
- `app/main.py`: FastAPI application with WebSocket endpoint `/ws/desk`
- `app/orchestrator/`: Conversation orchestrator with dynamic instructions
- `app/phases/`: Phase definitions and transitions
- `app/slots/`: Slot schema and store
- `app/skills/`: Microsoft Agent Framework Agent Skills and backend tools
- `app/adapters/`: Mock adapters for 113SF/CULTAS/AI Search
- `app/context/`: Call log and optional MAF session store for explicit future reuse

**Phases:**
1. **intake**: Initial intent capture when faultdesk owns the full conversation. In frontdesk handoff flows, this is seeded as complete.
2. **identity**: Customer verification (ID, name, address, contact)
3. **interview**: Fault diagnosis + line test + root cause identification
4. **visit**: Schedule proposal + confirmation + dispatch
5. **closing**: Resolution check + history recording + call wrap-up

### 4.4 Shared Package (voiceshared)

**Responsibilities:**
- Provide reusable components for both services
- Abstract Voice Live SDK complexity
- Define WebSocket protocols
- Provide OOB inference utilities

**Key Modules:**
- `voicelive/`: Voice Live SDK wrappers
- `tools/`: Tool registry system
- `ws_protocol/`: Frontend and handoff protocol definitions
- `oob/`: Azure OpenAI/Foundry client for non-real-time inference

## 5. Data Flow

### 5.1 Normal Call Flow

```
1. Browser → Frontdesk: Connect WebSocket + Start audio stream
2. Frontdesk: Create Voice Live session (triage agent)
3. Agent: "こんにちは、本日はどのようなご用件でしょうか？"
4. User: "インターネットが繋がらないんです"
5. Agent decides: route_to_fault_desk()
6. Frontdesk:
   - Connect to Faultdesk WebSocket
   - Send handoff_init message
   - Detach old Voice Live session
   - Bridge audio: Browser ↔ Faultdesk
7. Faultdesk: Receive handoff_init, create new session
8. Faultdesk Agent: "承知いたしました。故障状況を確認させていただきます..."
9. Phase progression: intake → identity → interview → visit → closing
10. Faultdesk: Send session_end message
11. Frontdesk: Close connections, output call log
```

### 5.2 Handoff Protocol Sequence

```
Frontdesk                            Faultdesk
   │                                    │
   │── WS connect /ws/desk ───────────> │
   │                                    │
   │── handoff_init ──────────────────> │
   │   {call_id, triage_summary,       │
   │    caller_attrs, source_phase}    │
   │                                    │
   │ <── handoff_ack ─────────────────  │
   │   {ready: true, desk_session_id}  │
   │                                    │
   │── audio (PCM16 base64) ──────────> │
   │ <── audio (PCM16 base64) ───────── │
   │ <── transcript / phase_changed /  │
   │     slots_snapshot / tool_call    │
   │                                    │
   │── control {action: end} ────────> │
   │ <── session_end ────────────────── │
```

## 6. Context Management Strategy

| Layer | Location | Content | Impact on Voice Live |
|-------|----------|---------|---------------------|
| **L1: Voice Live Session** | Active Voice Live session | Real-time spoken turns and tool-call decisions | Conversational context only |
| **L2: SlotStore** | `slots/store.py` | Cross-phase persistent slots | **Injected into instructions every turn** |
| **L3: MAF Skill Task** | Agent Framework + SkillsProvider | Dynamic `load_skill` execution with fresh AgentSession | Not flowing; only final short result returns |
| **L4: Business API Logs** | `adapters/` | Raw API responses | Not flowing (audit only) |
| **L5: Phase Transitions** | `orchestrator/phase_state.py` | Phase change history | UI/analytics only |
| **L6: Call Logs** | `context/call_log.py` | Complete call record | Exported to JSON at call end |

## 7. Technology Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn
- **Voice**: Azure Voice Live API (`azure-ai-voicelive` SDK)
- **Agent Framework**: Microsoft Agent Framework (Python)
- **LLM**: Azure OpenAI / Foundry
- **Frontend**: React 18, TypeScript, Vite, Web Audio API
- **Configuration**: pydantic-settings
- **Authentication**: Azure Entra ID (DefaultAzureCredential)
- **Testing**: pytest, pytest-asyncio, httpx
- **Package Management**: uv

## 8. Security Considerations

- **Authentication**: Services use Azure Managed Identity or API keys
- **Data Protection**: Call logs and customer information handled securely
- **Network Security**: WebSocket connections can be secured with TLS
- **Secrets Management**: Environment variables and Azure Key Vault integration

## 9. Monitoring and Observability

- **Structured Logging**: JSON logs with call_id correlation
- **Metrics**: Tool call latency, phase transition times, handoff success rates
- **Tracing**: Call flow tracking across services
- **Alerting**: Error rates, timeout detection, escalation triggers

## 10. Future Enhancements

1. **Additional Desk Services**: Billing, general inquiry, technical support
2. **PSTN Integration**: Direct phone call support via Azure Communication Services
3. **Advanced Analytics**: Call pattern analysis, customer satisfaction prediction
4. **Multi-Language Support**: Expand beyond Japanese
5. **Real-Time Monitoring Dashboard**: Live call visualization and intervention
6. **A/B Testing Framework**: Test different prompts and conversation flows
