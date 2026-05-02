# Azure Voice Live Support Agent

An end-to-end sample of a voice-based support agent built on Azure Voice Live API, featuring frontdesk triage, multi-desk handoff, and a fault-handling workflow powered by a Phase + Slot conversation model and skill-based agents implemented with Microsoft Agent Framework.

## Overview

This repository demonstrates a production-ready pattern for building intelligent voice support agents that can:

- **Natural triage and routing**: Frontdesk service handles initial customer interaction and routes to appropriate departments
- **Seamless handoff**: Voice stream bridging enables smooth transitions between services without disconnecting the customer
- **Structured conversation flow**: Phase + Slot system ensures complete information gathering while maintaining conversational flexibility
- **Modular skills**: Microsoft Agent Framework-based skills handle specific business logic (identity verification, fault diagnosis, scheduling, etc.)
- **Context management**: Multi-layer context separation for optimal performance and maintainability

## Architecture

```
┌─────────────┐
│   Browser   │ WebSocket (PCM16 24kHz audio)
└──────┬──────┘
       │
┌──────▼────────────────────────────────────────────┐
│  Frontdesk Service (Port 8000)                    │
│  - Voice Live session for triage                  │
│  - Route to appropriate desk via handoff manager  │
└──────┬────────────────────────────────────────────┘
       │ WebSocket handoff protocol
┌──────▼────────────────────────────────────────────┐
│  Faultdesk Service (Port 8001)                    │
│  - Voice Live orchestrator (single voice agent)   │
│  - Phase + Slot state management                  │
│  - Microsoft Agent Framework file-based skills    │
│    • skills/catalog/*/SKILL.md                    │
│    • backend tools in skills/tools.py             │
└───────────────────────────────────────────────────┘
```

## Repository Structure

```
azure-voicelive-support-agent/
├── docs/                      # Comprehensive documentation
│   ├── architecture.md
│   ├── handoff-protocol.md
│   ├── phase-and-slot-design.md
│   ├── skills-catalog.md
│   ├── context-strategy.md
│   └── adr/                   # Architecture Decision Records
├── services/
│   ├── frontdesk/             # Triage and routing service
│   └── faultdesk/             # Fault handling desk service
├── packages/
│   └── voiceshared/           # Shared components (Voice Live SDK wrappers, protocols)
├── frontend/                  # React UI with AudioWorklet
├── tests/                     # Integration and E2E tests
├── infra/                     # Azure infrastructure (Bicep)
└── tools/                     # Development tools
```

## Quick Start

### Prerequisites

- Python 3.11 or later
- Node.js 18 or later
- [uv](https://docs.astral.sh/uv/) package manager
- Azure subscription with:
  - Azure Voice Live API access
  - Azure OpenAI Service or Foundry endpoint

### Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/ishidahra01/azure-voicelive-support-agent.git
cd azure-voicelive-support-agent
```

2. Install Python dependencies:
```bash
uv sync
```

3. Configure environment variables:
```bash
# Copy example files
cp services/frontdesk/.env.example services/frontdesk/.env
cp services/faultdesk/.env.example services/faultdesk/.env

# Edit .env files with your Azure endpoints.
# Leave API keys blank to use Microsoft Entra ID.
```

Model configuration is intentionally split by runtime surface:

- `VOICE_LIVE_MODEL` is the Voice Live realtime model identifier. The shared Voice Live wrapper passes it to `azure.ai.voicelive.aio.connect(..., model=...)`, which is the current SDK/API place where the Voice Live model is selected.
- `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` are preferred for the faultdesk Microsoft Agent Framework skill agent. When `FOUNDRY_PROJECT_ENDPOINT` is set, the agent uses `FoundryChatClient`.
- `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_MODEL` are the fallback text backend for the MAF skill agent when `FOUNDRY_PROJECT_ENDPOINT` is blank. They can also be used by non-Foundry text/OOB code paths.

For example, `VOICE_LIVE_MODEL=gpt-realtime` and `FOUNDRY_MODEL=gpt-4o` are separate choices and should not be treated as the same deployment.

4. Install frontend dependencies:
```bash
cd frontend
npm install
```

### Running Locally

Use the provided PowerShell script to start all services:

```powershell
.\tools\run-local.ps1
```

Or start services individually:

```bash
# Terminal 1: Faultdesk service (must start first)
cd services/faultdesk
uv run uvicorn app.main:app --port 8001

# Terminal 2: Frontdesk service
cd services/frontdesk
uv run uvicorn app.main:app --port 8000

# Terminal 3: Frontend
cd frontend
npm run dev
```

Access the application at `http://localhost:5173`

## Key Features

### 1. Phase + Slot System

The fault desk uses a structured conversation model:

- **Phases**: intake → identity → interview → visit → closing
- **Slots**: Required and optional information pieces within each phase
- **Flexibility**: Jump between phases naturally while maintaining context

### 2. Handoff Protocol

Seamless service-to-service handoff:
- WebSocket-based bridge maintains audio stream
- Context transfer via `handoff_init` message
- Transparent to the end user

### 3. Microsoft Agent Framework Skills

Faultdesk uses the Microsoft Agent Framework file-based Agent Skills pattern:
- Skill instructions and references live under `services/faultdesk/app/skills/catalog/<skill-name>/SKILL.md`
- A single faultdesk MAF `Agent` discovers those skills through `SkillsProvider(skill_paths=...)`
- Backend actions live in `services/faultdesk/app/skills/tools.py` so they can update SlotStore and CallLog in-process
- Voice Live calls the skill agent through orchestrator tools; skills have no direct audio I/O

### 4. Multi-Layer Context Management

- **L1**: Voice Live conversation history (with summarization)
- **L2**: SlotStore (cross-phase persistent state)
- **L3**: Faultdesk MAF AgentSession with file-based Agent Skills
- **L4**: Business API logs (audit trail)
- **L5**: Phase transition history (UI/analytics)
- **L6**: Call logs (JSON export)

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Handoff Protocol Specification](docs/handoff-protocol.md)
- [Phase + Slot Design](docs/phase-and-slot-design.md)
- [Skills Catalog](docs/skills-catalog.md)
- [Context Management Strategy](docs/context-strategy.md)
- [Architecture Decision Records](docs/adr/)

## Testing

```bash
# Run all tests
uv run pytest

# Run specific test suites
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/

# Run with coverage
uv run pytest --cov=services --cov=packages
```

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn
- **Voice**: Azure Voice Live API (`azure-ai-voicelive` SDK)
- **Agent Framework**: Microsoft Agent Framework (Python)
- **LLM**: Azure OpenAI / Foundry
- **Frontend**: React 18, TypeScript, Vite, Web Audio API
- **Configuration**: pydantic-settings
- **Authentication**: Azure Entra ID (DefaultAzureCredential)
- **Testing**: pytest, pytest-asyncio, httpx
- **Package Management**: uv

## Contributing

This is a sample repository demonstrating best practices for Azure Voice Live applications. Feel free to use it as a starting point for your own implementations.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acceptance Criteria (Initial Version)

- [x] Two manual E2E scenarios work locally (straight path + back-and-forth)
- [x] Frontend displays Phase Badge + Slot Checklist + Handoff Indicator
- [x] Call logs output as JSON per call_id (frontdesk + faultdesk integrated)
- [x] Unit tests pass: SlotStore, PhaseState, Skills, Handoff protocol
- [x] Complete documentation in `docs/`
- [x] README with environment variables and quick start guide
