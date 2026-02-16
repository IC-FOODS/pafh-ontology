# Plugin Contract Matrix (KnowBrow + CMS + Plugin FEs)

Date: 2026-02-16
Owner: Cross-repo alignment (KnowBrow platform + GraphMap + Food Omics + CMS)
Status: Working draft

## Scope

This matrix tracks contract alignment across:

- `knowbrow` (FastAPI + Django/Wagtail embed host)
- `graphmap` (plugin FE)
- `food-omics-explorer` (plugin FE)
- `ic-foods-cms` (site skin; currently architecture/docs-heavy, not runtime embed authority)

## Matrix

Legend:

- `✅` implemented and aligned
- `⚠️` partially implemented / drift
- `❌` missing

| Contract area | KnowBrow API | KnowBrow CMS Embed Layer | GraphMap FE | Food Omics FE | Generalizable? |
|---|---|---|---|---|---|
| Versioned plugin contract docs | ✅ (`docs/PLUGIN_CONTRACT.md` + OpenAPI/JSON Schemas/fixtures) | n/a | ⚠️ consumes behavior but not explicitly version-checked | ⚠️ consumes behavior but not explicitly version-checked | Yes |
| `GET /api/capabilities` bootstrap endpoint | ✅ (implemented + unit tests) | n/a | ❌ does not bootstrap with capabilities call | ❌ does not bootstrap with capabilities call | Yes |
| Runtime modes (`demo` / `integrated`) | ✅ response model + feature/source flags implemented | n/a | ⚠️ has anonymous/auth behavior but not contract-driven provider split | ⚠️ has static/api mode but not capabilities-driven provider split | Yes |
| Source access scoping (`sources.accessible`) | ✅ server-side enforcement in search/map/data-sources + capabilities payload | n/a | ⚠️ uses `/api/data-sources` but not explicitly bound to capabilities contract | ⚠️ dataset endpoints only; no capabilities/source scoping yet | Yes |
| Iframe URL params (`api`, `theme`, `node`, `sources`, optional plugin params) | ✅ supported by embed page | ✅ generated in `build_iframe_src` | ✅ consumed | ✅ consumed | Yes |
| `postMessage` config envelope (`type=config`, `api`, `theme`, `dataSources`, etc.) | ✅ model + template emit envelope | ✅ sent on iframe load | ✅ consumed | ✅ consumed | Yes |
| `authToken` injection via postMessage for embedded auth | ❌ not emitted by current embed config payload | ❌ missing in `build_post_message_config` | ⚠️ expects/accepts it but may not receive it | ⚠️ expects/accepts it but may not receive it | Yes |
| Theme token handoff (`themeTokens`) | ✅ generated in embed model | ✅ sent | ⚠️ can receive config, but token application is plugin-specific | ⚠️ uses own theming model, not full token contract yet | Mostly |
| Plugin -> host events (`select`, `navigate`) | ⚠️ implied contract only | ⚠️ no receiver contract documented/implemented end-to-end | ⚠️ marked planned | ⚠️ not standardized | Yes |
| Plugin-specific persistence/materialization APIs | ⚠️ GraphMap CRUD/share/version APIs exist; no generic plugin materialization standard | ⚠️ page can bind GraphMap share/config | ✅ GraphMap uses these APIs | ❌ Omics materialization workflow not yet implemented | Partially |
| Dataset contract for Omics (`/api/datasets/*`) | ✅ available | ⚠️ embed page passes params but no Omics-specific bootstrap contract | n/a | ⚠️ partly wired; config still local-first | Omics-specific API, general pattern reusable |

## Security Mitigation Checklist (Mapped to Vulnerability List)

1. Token exfiltration risk in-browser
- Mitigation:
  - Remove `targetOrigin='*'` fallback; fail closed when origin cannot be resolved.
  - Strict allowlist for iframe origins in CMS model validation and headers.
  - Keep tokens in memory only in plugins (no localStorage/sessionStorage).
- Repos:
  - `knowbrow`, `graphmap`, `food-omics-explorer`

2. Over-privileged token design
- Mitigation:
  - Mint dedicated embed token with narrow audience + scopes.
  - Do not reuse broad user/session token for iframe payload.
- Repos:
  - `knowbrow`

3. Replay window
- Mitigation:
  - Very short TTL (for example 2-5 minutes).
  - Include `jti` and enforce freshness/rotation policy.
  - Optional one-time use nonce for high-risk operations.
- Repos:
  - `knowbrow`

4. Logging leakage
- Mitigation:
  - Redact `Authorization`, `authToken`, and related fields from logs/errors/telemetry.
  - Add tests for redaction and no-token-in-logs guardrails.
- Repos:
  - `knowbrow`, `graphmap`, `food-omics-explorer`

5. Weak contract guarantees
- Mitigation:
  - Publish versioned schema for iframe URL params + postMessage payload.
  - Add contract tests against this schema in plugin repos.
- Repos:
  - `knowbrow`, `graphmap`, `food-omics-explorer`

6. No explicit handshake/ack model
- Mitigation:
  - Define standard host/plugin events: `ready`, `config`, `auth-refresh`, `error`, `select`, `navigate`.
  - Require plugin ack for config receipt and token refresh failures.
- Repos:
  - `knowbrow`, `graphmap`, `food-omics-explorer`

7. CSP/frame hardening gaps
- Mitigation:
  - Tighten `frame-ancestors` / origin policy and align with known plugin hosts.
  - Add explicit embed origin configuration path and tests.
- Repos:
  - `knowbrow`

8. Threat-model separation and documentation drift
- Mitigation:
  - Document KnowBrow runtime files as source of truth.
  - Label aspirational architecture docs as target state.
- Repos:
  - `ic-foods-cms`, `food-omics-explorer`, `graphmap`

## Evidence Pointers

- Plugin contract + capabilities requirement:
  - `knowbrow/docs/PLUGIN_CONTRACT.md`
  - `knowbrow/backend/fastapi/main.py`
  - `knowbrow/backend/fastapi/tests/test_capabilities_endpoint.py`
  - `knowbrow/scripts/test_fastapi_contract.sh`
  - `knowbrow/.github/workflows/ci.yml` (conditional plugin-contract test job)
- CMS embed host behavior:
  - `knowbrow/backend/django/graphs/models.py`
  - `knowbrow/backend/django/graphs/templates/graphs/visualization_embed_page.html`
  - `knowbrow/backend/django/graphs/tests/test_visualization_embed_page.py`
- GraphMap FE integration behavior:
  - `graphmap/src/lib/embedConfig.js`
  - `graphmap/src/config/api.js`
  - `graphmap/src/services/graphmapClient.js`
  - `graphmap/src/App.jsx`
- Omics FE integration behavior:
  - `food-omics-explorer/src/lib/embedConfig.js`
  - `food-omics-explorer/src/api/dataLoader.js`
  - `food-omics-explorer/PLANS/PLUGIN_RUNTIME_CONTRACT.md`
- IC-FOODS CMS repo current role (planned architecture, not runtime authority):
  - `ic-foods-cms/PLANS/ARCHITECTURE.md`

## Issues To Create By Repo (Updated Priority)

## P0-Security (Do first)

1. Repo: `knowbrow`
- Title: `Embed security: strict iframe origin handling (no '*' fallback) + origin allowlist`
- Covers: vulnerabilities #1, #7
- Acceptance criteria:
  - iframe postMessage never sends config to `*` in production paths.
  - embed origins validated against configured allowlist.
  - tests for invalid/missing origin behavior (fail closed).

2. Repo: `knowbrow`
- Title: `Embed auth token service: short-lived scoped token for iframe config payload`
- Covers: vulnerabilities #2, #3
- Acceptance criteria:
  - `build_post_message_config()` can include dedicated `authToken` when authenticated.
  - token includes audience + minimal scopes + short TTL + `jti`.
  - token never appears in iframe URL query parameters.

3. Repo: `knowbrow`
- Title: `Secrets hygiene: redact auth tokens/Authorization from logs and error payloads`
- Covers: vulnerability #4
- Acceptance criteria:
  - centralized redaction for sensitive headers/fields.
  - automated tests verify no token leakage in error/log paths.

## P0-Contract Conformance (Immediately after P0-Security)

4. Repo: `graphmap`
- Title: `Contract bootstrap: call /api/capabilities on startup and gate runtime mode`
- Covers: vulnerability #5 (plugin side)
- Acceptance criteria:
  - startup calls `/api/capabilities` with bearer token when available.
  - `demo` mode disables privileged actions and constrains sources.
  - `integrated` mode enables actions by capability flags.

5. Repo: `food-omics-explorer`
- Title: `Contract bootstrap + provider split (DemoProvider/IntegratedProvider)`
- Covers: vulnerability #5 (plugin side)
- Acceptance criteria:
  - provider split implemented.
  - `/api/capabilities` bootstrap determines mode.
  - integrated mode uses API provider; demo mode uses fixture/static provider.

6. Repo: `graphmap`
- Title: `Embedded auth hardening: keep embed authToken in memory only`
- Covers: vulnerability #1/#4 (plugin side)
- Acceptance criteria:
  - no persistence of embed token to localStorage/sessionStorage.
  - explicit test/assertion around embed-token storage behavior.

7. Repo: `food-omics-explorer`
- Title: `Embedded auth hardening: keep embed authToken in memory only`
- Covers: vulnerability #1/#4 (plugin side)
- Acceptance criteria:
  - no persistence of embed token to localStorage/sessionStorage.
  - explicit test/assertion around embed-token storage behavior.

## P1-Protocol and Docs Hardening

8. Repo: `knowbrow`
- Title: `Publish canonical iframe config schema (URL + postMessage), versioned`
- Covers: vulnerability #5
- Acceptance criteria:
  - required/optional keys and auth semantics documented.
  - JSON Schema + examples for GraphMap and Omics.

9. Repo: `knowbrow`
- Title: `Define standard host/plugin event protocol (ready/config/auth-refresh/error/select/navigate)`
- Covers: vulnerability #6
- Acceptance criteria:
  - event schema and lifecycle documented.
  - reference host-side sender/listener utility.

10. Repo: `graphmap`
- Title: `Implement host/plugin event protocol and ack flow`
- Covers: vulnerability #6
- Acceptance criteria:
  - emits `ready`, handles `config`/`auth-refresh`, emits standardized `select`/`navigate`.

11. Repo: `food-omics-explorer`
- Title: `Implement host/plugin event protocol and ack flow`
- Covers: vulnerability #6
- Acceptance criteria:
  - emits `ready`, handles `config`/`auth-refresh`, emits standardized events as needed.

12. Repo: `ic-foods-cms`
- Title: `Docs sync: mark KnowBrow VisualizationEmbedPage as runtime contract authority`
- Covers: vulnerability #8
- Acceptance criteria:
  - architecture doc points to canonical KnowBrow runtime contract and tests.
  - planned-state sections explicitly labeled.

## P2-Feature Roadmap (After security + protocol stabilization)

13. Repo: `food-omics-explorer`
- Title: `Integrated mode config source: /api/datasets/{id}/config`
- Acceptance criteria:
  - integrated mode reads runtime config from KnowBrow API.
  - demo mode remains fixture/local compatible.

14. Repo: `knowbrow`
- Title: `Generalized plugin materialization contract (create/list/version/publish)`
- Acceptance criteria:
  - lifecycle contract defined and documented.
  - permissions/provenance rules defined.

15. Repo: `food-omics-explorer`
- Title: `Implement materialization workflow with LinkML-guided validation`
- Acceptance criteria:
  - mapping/query/validation/save flow functional against generalized contract.

## Order Of Operations (Cross-Repo, Updated)

1. `knowbrow` P0-Security issues #1, #2, #3 (sequential)
- Establish secure host baseline before broad FE adoption.

2. `graphmap` + `food-omics-explorer` P0-Contract issues #4 and #5 (parallel)
- Bring both plugins onto capabilities-driven mode contract.

3. `graphmap` + `food-omics-explorer` P0-Contract issues #6 and #7 (parallel)
- Ensure plugin-side embed auth handling is memory-only and non-leaky.

4. `knowbrow` P1 issues #8 and #9
- Freeze canonical schema + event protocol.

5. `graphmap` + `food-omics-explorer` P1 issues #10 and #11
- Implement protocol conformance and acknowledgements.

6. `ic-foods-cms` P1 issue #12
- Align downstream docs with runtime source of truth.

7. P2 issues #13, #14, #15
- Resume product feature expansion on stable secure contract.

## Suggested Program Cadence

- Sprint 1: P0-Security + P0-Contract
- Sprint 2: P1 protocol/docs hardening
- Sprint 3+: P2 feature roadmap (Omics integrated config + materialization)

## Definition of Done (Program)

- GraphMap and Food Omics pass shared contract smoke tests for:
  - capabilities bootstrap,
  - demo/integrated mode gating,
  - iframe config ingestion,
  - source scoping behavior.
- Security smoke checks pass for:
  - no token in URL,
  - no token in logs,
  - strict origin enforcement,
  - short-lived scoped embed token claims.
- KnowBrow plugin docs and CMS-facing docs match runtime truth.
