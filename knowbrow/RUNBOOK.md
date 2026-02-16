# KnowBrow Staging Runbook

Manual fallback for staging deployment and verification.

## Scope

This runbook covers:
- infrastructure startup via production `docker-compose.yml`,
- Django/FastAPI/Oxigraph readiness checks,
- proxy route verification through Caddy,
- rollback and common failure recovery.

This runbook does not cover CI/CD automation (tracked separately in `.github/workflows/ci.yml`).

## Prerequisites

1. Docker + Docker Compose plugin installed.
2. Access to the deployment host and this repo checkout.
3. Staging DNS/host mapped to the machine (or use `localhost`).
4. Required secrets and config values prepared.

## 1) Prepare Environment

From repo root:

```bash
cd knowbrow
cp .env.prod.example .env
```

Edit `.env` with staging-safe values:

1. `DOMAIN` (staging host, or `localhost` for local TLS).
2. `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, `INTERNAL_API_KEY`, `DJANGO_USER`, `DJANGO_PASSWORD` (non-default secrets).
3. `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_CORS_ALLOWED_ORIGINS`.
4. `DJANGO_SETTINGS_MODULE=sparql_app.settings_production`.
5. `OXIGRAPH_SPARQL_URL=http://oxigraph:7878/query`.

## 2) Start Production Stack

Use production compose only (no override):

```bash
docker compose -f docker-compose.yml up -d --build
```

Check container health/state:

```bash
docker compose -f docker-compose.yml ps
docker compose -f docker-compose.yml logs --no-color --tail=200 django
docker compose -f docker-compose.yml logs --no-color --tail=200 fastapi
docker compose -f docker-compose.yml logs --no-color --tail=200 caddy
```

Expected:
- `db`, `django`, `fastapi`, `oxigraph`, `caddy` are `Up`.
- Django starts via `backend/django/entrypoint.sh` (migrate + gunicorn).

## 3) Seed/Verify Triple Store (if needed)

If data is not already present:

```bash
./scripts/load_oxigraph.sh
```

Quick count check:

```bash
curl -k -sS -X POST "https://localhost/sparql" \
  -H "Content-Type: application/sparql-query" \
  -d "SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }"
```

## 4) API and Proxy Smoke Tests

Run Caddy route smoke checks:

```bash
./scripts/smoke_caddy_routes.sh
```

Optional non-local host:

```bash
BASE_URL=https://staging.your-domain.tld ./scripts/smoke_caddy_routes.sh
```

Expected:
- `/admin` and `/cms` route to Django (not fallback text).
- `/health` routes to FastAPI.
- `/docs` and `/openapi.json` return `404` in production.
- `/internal` and `/internal/query` return `404` from proxy.

## 5) Backend Test Validation

Run key backend tests in containers:

```bash
docker compose -f docker-compose.yml exec -T django python manage.py test \
  graphs.tests.test_internal_contracts \
  graphs.tests.test_datasource_workflow

docker compose -f docker-compose.yml exec -T fastapi sh -lc \
  'cd /app && python -m unittest discover -s tests -p "test_*.py"'
```

## 6) Release Gate (Staging)

Staging release is accepted when all are true:

1. Compose services are up without crash loops.
2. Caddy route smoke test passes.
3. Django + FastAPI test slices above pass.
4. `/health` is healthy and production-only API docs are not publicly reachable.
5. Oxigraph query returns expected dataset metadata/counts.

## Rollback

To roll back to a prior known-good commit:

```bash
git checkout <known-good-commit-or-tag>
docker compose -f docker-compose.yml up -d --build
```

If needed, restore previous `.env` values from backup and redeploy.

## Common Failures

1. `400 Bad Request` / CSRF errors:
- Verify `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.

2. FastAPI cannot query Django internal endpoints:
- Ensure `INTERNAL_API_KEY` matches in both services.

3. SPARQL queries return empty/unexpected results:
- Verify `OXIGRAPH_SPARQL_URL` and that seed data is loaded.
- Confirm Oxigraph container is up and reachable inside network.

4. Caddy serves fallback `KnowBrow API` unexpectedly:
- Recheck Caddy route matchers and service health.
- Re-run `./scripts/smoke_caddy_routes.sh`.
