# KnowBrow

Platform core for the KnowGrow knowledge graph ecosystem.

## Overview

KnowBrow provides the backend infrastructure: Django/Wagtail CMS, FastAPI adapter registry, and data layer orchestration. Frontend visualization tools (GraphMap, Food Omics Explorer) are standalone apps in their own repos.

## Architecture

```
knowbrow/
├── backend/
│   ├── django/          ← Django + Wagtail CMS, models, auth, write-back
│   │   ├── graphs/      ← Platform app (DataSource, GraphMapConfig, permissions)
│   │   ├── sites/icfoods/  ← IC-FOODS CMS site (submodule → IC-FOODS/ic-foods-cms)
│   │   └── sparql_app/  ← Django project settings, URLs
│   └── fastapi/         ← Adapter registry, API gateway
│       └── adapters/    ← Oxigraph adapter, DjangoDBAdapter, WikidataAdapter
├── docker-compose.yml   ← Django, FastAPI, Postgres, Oxigraph, Ontop
├── oxigraph/            ← Ontology + seed data for Oxigraph
├── ontop/               ← Ontop virtual SPARQL endpoint
└── PLANS/               ← Architecture and development docs
```

## Services (Docker Compose)

| Service | Port | Role |
|---------|------|------|
| `caddy` | 80/443 | Public reverse proxy (production entrypoint) |
| `django` | internal | Wagtail CMS + REST API + auth |
| `fastapi` | internal | Adapter registry + query gateway |
| `db` | internal | PostgreSQL |
| `oxigraph` | internal | Oxigraph SPARQL triple store |
| `ontop` | 8080 | Ontop virtual SPARQL endpoint |

## Development

```bash
cp .env.dev.example .env
docker compose up --build
# Dev override exposes Django :8010, FastAPI :8001, Oxigraph :7878
```

## Production

```bash
cp .env.prod.example .env
docker compose -f docker-compose.yml up -d --build
# Public entrypoint: Caddy on :80/:443
```

## Ecosystem

| Repo | Role |
|------|------|
| **UKnowGrow/knowbrow** | Platform core (this repo) |
| [UKnowGrow/graphmap](https://github.com/UKnowGrow/graphmap) | Knowledge graph visualization (extracted 2026-02-13) |
| [IC-FOODS/food-omics-explorer](https://github.com/IC-FOODS/food-omics-explorer) | Food omics visualization |
| [IC-FOODS/ic-foods-cms](https://github.com/IC-FOODS/ic-foods-cms) | IC-FOODS Wagtail CMS site |

See [PLANS/ARCHITECTURE.md](PLANS/ARCHITECTURE.md) for full architecture documentation.

## Plugin Contract

For sandboxed frontend plugin development (GraphMap, Food Omics Explorer, and future plugins), use the versioned contract pack:

- `/Users/mateolan/Documents/GitHub/knowbrow/docs/PLUGIN_CONTRACT.md`
- `/Users/mateolan/Documents/GitHub/knowbrow/docs/plugin-contract/openapi.yaml`
- `/Users/mateolan/Documents/GitHub/knowbrow/docs/plugin-contract/schemas/`
- `/Users/mateolan/Documents/GitHub/knowbrow/docs/plugin-contract/fixtures/`

Run the FastAPI plugin capability contract test in Docker:

```bash
./scripts/test_fastapi_contract.sh
```
