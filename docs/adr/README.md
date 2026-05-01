# Architecture Decision Records (ADR)

This directory contains Architecture Decision Records documenting key design decisions for the Azure Voice Live Support Agent project.

## What are ADRs?

Architecture Decision Records (ADRs) are lightweight documents that capture important architectural decisions along with their context and consequences. Each ADR describes:

- The **context** and problem being addressed
- The **decision** that was made
- The **rationale** behind the decision
- The **consequences** (both positive and negative)
- **Alternatives** that were considered

## Format

Each ADR follows this structure:

```markdown
# ADR NNNN: Title

## Status
[Proposed | Accepted | Deprecated | Superseded]

## Context
[What is the issue that we're seeing that is motivating this decision or change?]

## Decision
[What is the change that we're proposing and/or doing?]

## Rationale
[Why did we choose this option? What are the trade-offs?]

## Consequences
[What becomes easier or more difficult to do because of this change?]

## Alternatives Considered
[What other options were considered and why were they rejected?]

## References
[Links to relevant resources]
```

## Index

- [ADR-0001: Monorepo Structure](0001-monorepo.md) - Decision to use a monorepo for all services and packages
- [ADR-0002: Handoff via WebSocket Bridge](0002-handoff-via-ws-bridge.md) - How calls are transferred between services
- [ADR-0003: Microsoft Agent Framework for Skills](0003-agent-framework-for-skills.md) - Using Agent Framework for business logic
- [ADR-0004: Phase + Slot Conversation Model](0004-phase-plus-slot.md) - Structured yet flexible conversation management

## When to Write an ADR

Write an ADR when making decisions that:

- Affect the system's structure or architecture
- Have long-term implications
- Are difficult or expensive to reverse
- Require buy-in from multiple stakeholders
- Involve significant trade-offs
- Set important precedents

## ADR Lifecycle

1. **Proposed**: Initial draft, under discussion
2. **Accepted**: Decision has been made and is being implemented
3. **Deprecated**: Decision is no longer recommended but still in use
4. **Superseded**: Replaced by a newer decision (reference the superseding ADR)

## Contributing

When proposing a new ADR:

1. Copy the template from this README
2. Number it sequentially (check existing ADRs)
3. Fill in all sections
4. Submit for review
5. Update this README's index once accepted

## References

- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) by Michael Nygard
- [ADR GitHub Organization](https://adr.github.io/)
- [Architecture Decision Records](https://github.com/joelparkerhenderson/architecture-decision-record)
