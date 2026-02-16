# KnowBrow Production Implementation Checklist

Use this checklist to track deployment readiness for DigitalOcean while preserving local dev speed.

## Repo and workflow

- [x] Keep a single repo with environment-specific compose layering.
- [x] Keep production-safe defaults in `docker-compose.yml`.
- [x] Keep local dev behavior in `docker-compose.override.yml`.
- [ ] Enforce protected branch rules for `main` in GitHub settings.
- [ ] Require PR review and passing CI checks before merge to `main`.

## Security hardening

- [x] Removed Docker socket mount from production compose.
- [x] Restricted FastAPI docs and OpenAPI schema at proxy (`/docs`, `/openapi.json` return `404`).
- [x] Removed public `api/test` route from Django URLs.
- [x] Made internal API key checks fail closed if `INTERNAL_API_KEY` is unset.
- [x] Replaced insecure default FastAPI service credentials with env-only values.
- [ ] Rotate and store production secrets in a secure secret manager.

## Configuration and env hygiene

- [x] Standardized on `OXIGRAPH_SPARQL_URL`.
- [x] Added `.env.dev.example` for local defaults.
- [x] Added `.env.prod.example` for production template.
- [x] Updated `.env.example` to a shared baseline.
- [ ] Ensure production `.env` is present only on deployment host (never committed).

## Runtime reliability

- [x] Removed production source-code bind mounts for Django/FastAPI containers.
- [x] Added named volume for Django media (`django_media`).
- [x] Added shared named volume for Ontop runtime properties (`ontop_runtime`).
- [ ] Define backup/restore automation for `postgres_data`, `oxigraph_data`, and `django_media`.
- [ ] Define rollback procedure by image tag and git SHA in deployment docs.

## CI/CD guardrails

- [x] CI now uses `OXIGRAPH_SPARQL_URL`.
- [x] CI validates production compose does not mount Docker socket.
- [x] CI validates production compose does not bind-mount Django/FastAPI source.
- [ ] Add image tag pinning policy checks (no `latest` in production images).
- [ ] Add release job for staging deploy + smoke tests before production promotion.

## DigitalOcean cutover checklist

- [ ] Provision host and firewall rules (open only `22`, `80`, `443`; restrict `22`).
- [ ] Configure DNS `A/AAAA` to host and verify TLS issuance via Caddy.
- [ ] Copy `.env.prod.example` -> `.env` and set all production secrets.
- [ ] Deploy with `docker compose -f docker-compose.yml up -d --build`.
- [ ] Run smoke tests (`scripts/smoke_caddy_routes.sh`).
- [ ] Verify health endpoint (`/health`) and CMS login flow.
- [ ] Run backup restore drill before go-live.
