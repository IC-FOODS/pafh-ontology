# Plugin Contract for Frontend Integrations

This document defines the minimum contract for pluggable frontends (for example: GraphMap and Food Omics Explorer) that are developed in separate repos.

## Goals

- Keep plugin development sandboxed from core stack risk.
- Provide a stable API and schema contract that frontend teams can target.
- Support two runtime modes:
  - demo mode for unauthenticated users (fixture/static data),
  - integrated mode for authenticated and authorized users.

## Contract version

Current version: `2026-02-16`.

Every plugin should declare the contract version it targets in `plugin.manifest.json`.

## Required runtime endpoint

- `GET /api/capabilities`

Plugins must bootstrap by calling `/api/capabilities`.

Use response rules:

1. `mode=demo`:
- load fixture data only,
- disable save/share/write-back interactions,
- show demo-safe visualizations.

2. `mode=integrated`:
- call runtime APIs,
- enable save/share/write-back only when capability flags allow,
- scope data access to `sources.accessible`.

## Cross-repo alignment matrix

- `docs/PLUGIN_CONTRACT_MATRIX.md` — contract status by repo, required issues, and execution order.
## Reference artifacts

- OpenAPI surface: `docs/plugin-contract/openapi.yaml`
- JSON Schemas:
  - `docs/plugin-contract/schemas/plugin-manifest.schema.json`
  - `docs/plugin-contract/schemas/capabilities-response.schema.json`
  - `docs/plugin-contract/schemas/search-result.schema.json`
- Fixtures:
  - `docs/plugin-contract/fixtures/plugin.manifest.example.json`
  - `docs/plugin-contract/fixtures/capabilities.unauthenticated.json`
  - `docs/plugin-contract/fixtures/capabilities.authenticated.json`
  - `docs/plugin-contract/fixtures/search.demo.json`

## Plugin repo implementation pattern

Each plugin repo should implement two providers with identical output shape:

1. `DemoProvider`
- uses fixtures only,
- does not require auth.

2. `IntegratedProvider`
- uses KnowBrow APIs,
- respects capability flags and source scoping.

The UI should consume one provider interface and never branch on raw backend payload shape.

## CI expectations for plugin repos

At minimum:

1. Validate `plugin.manifest.json` against schema.
2. Validate fixture JSON files against schemas.
3. Run contract smoke tests:
- unauthenticated bootstrap expects `mode=demo`,
- authenticated bootstrap expects `mode=integrated`.

Reference command in this repo:

```bash
./scripts/test_fastapi_contract.sh
```

## Security notes

- Capability flags are UX hints, not authorization.
- Backend endpoints must always enforce authorization server-side.
- Plugins must not treat demo fixtures as trusted user data.
