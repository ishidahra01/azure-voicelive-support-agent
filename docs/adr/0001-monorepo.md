# ADR 0001: Monorepo Structure

## Status
Accepted

## Context
We need to decide how to organize code for a system with multiple services (frontdesk, faultdesk), shared components, and a frontend application.

Options considered:
1. **Monorepo**: All code in a single repository
2. **Polyrepo**: Separate repository for each service
3. **Hybrid**: Shared package in separate repo, services together

## Decision
We adopt a **monorepo structure** using uv workspace for Python packages and a single repository root.

## Rationale

### Advantages of Monorepo:
- **Simplified Development**: Developers can work on frontend, backend, and shared code simultaneously
- **Atomic Changes**: Cross-service changes can be committed atomically
- **Easier Testing**: Integration tests can span multiple services easily
- **Consistent Tooling**: Single CI/CD pipeline, unified linting/formatting
- **Sample Project**: As an end-to-end sample, keeping everything together aids understanding
- **Version Consistency**: No need to manage inter-package version compatibility

### Mitigated Disadvantages:
- **Repository Size**: Manageable for a sample project (not a large-scale production system)
- **Build Times**: Development workflows remain fast with selective testing
- **Access Control**: Not a concern for open-source sample

## Implementation

```
azure-voicelive-support-agent/
├── pyproject.toml              # Root workspace configuration
├── services/
│   ├── frontdesk/              # Independent service with own pyproject.toml
│   └── faultdesk/              # Independent service with own pyproject.toml
├── packages/
│   └── voiceshared/            # Shared Python package
├── frontend/                   # React application (separate package.json)
├── docs/                       # Shared documentation
├── tests/                      # Integration tests across services
└── infra/                      # Shared infrastructure templates
```

**uv Workspace Configuration** (`pyproject.toml`):
```toml
[tool.uv.workspace]
members = [
    "services/frontdesk",
    "services/faultdesk",
    "packages/voiceshared"
]
```

## Consequences

### Positive:
- Easy to demonstrate end-to-end flow (primary goal as a sample)
- Lower barrier to entry for developers
- Simplified local development setup
- Shared CI/CD configuration

### Negative:
- All services must use compatible Python versions
- Larger git clone size
- Cannot independently version services (acceptable for sample)

### Neutral:
- Must establish clear module boundaries despite shared repo
- Need conventions to prevent tight coupling

## Alternatives Considered

### Polyrepo
**Rejected because**:
- Too much overhead for a sample project
- Harder to demonstrate end-to-end flow
- Version synchronization complexity
- Multiple repositories to maintain

### Hybrid
**Rejected because**:
- Added complexity without clear benefit for a sample
- Still requires managing multiple repositories

## References
- [Monorepo vs Polyrepo Debate](https://monorepo.tools/)
- [Google's Monorepo Approach](https://cacm.acm.org/magazines/2016/7/204032-why-google-stores-billions-of-lines-of-code-in-a-single-repository/fulltext)
- [uv Workspace Documentation](https://docs.astral.sh/uv/concepts/workspaces/)
