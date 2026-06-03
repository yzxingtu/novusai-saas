# Release Readiness Cross Audit

## Goal

Bring the current main branch closer to a shippable SaaS baseline by fixing the concrete blockers found in the latest cross audits instead of hiding them behind compatibility paths or broad claims.

## Requirements

- Keep the work on `main`.
- Do not reintroduce online search, web fetch, or weather hardcoding into the core AI runtime. Skill/package capabilities must stay metadata-driven and plugin-owned.
- Remove real legacy compatibility surfaces where the current public contract is already clear. Do not delete ordinary business fallback, failover, or error handling.
- Preserve tenant isolation, active-plan entitlement checks, scheduler run-key reliability, trace propagation, and queue dispatch truth.
- Production compose must represent immutable image deployment and production acceptance must not reuse stale AI smoke evidence after guarded runtime/deploy changes.
- Frontend AI health history must request 60 real points per provider, show gray bars only for missing loaded history, and show an explicit error state for failed history loads.
- Every changed AI-dialogue test or smoke-adjacent test must carry a `Test type:` classification and must not use weak/self-fulfilling assertions.

## Acceptance Criteria

- Targeted backend pytest and ruff checks pass for the touched AI, scheduler, production acceptance, and migration files.
- Targeted frontend type/test checks pass for AI health and API contract adapters, or any browser/e2e blocker is stated precisely.
- `docker compose --env-file ops\production.env.example -f docker-compose.prod.yml config --quiet` succeeds and expanded production config contains no `build:` blocks.
- Alembic graph/lint checks pass for added migrations.
- Final answer distinguishes code-level readiness from external production gates such as real provider smoke, capacity testing, DAST, backup restore, and operator signoff.
