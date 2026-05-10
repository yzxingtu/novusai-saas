# NovusAI Release Readiness Report

Date: 2026-05-10

Accepted runtime commit: `1625841d8d527e6246cc17b47394afb20dbb9597`

Branch: `main`

Verdict: release candidate accepted for production-environment deployment checks.

## Summary

The local production acceptance gates passed for the accepted runtime commit
above. This report records the release evidence that was available after the
final acceptance run, so operators do not need to reconstruct the decision from
chat history or ignored local artifacts.

Release state:

- Git state during the cross-audit run: clean working tree at the accepted
  runtime commit.
- Probe status: `overall_status=passed`.
- Gate counts: `23 passed / 0 failed / 0 blocked`.
- AI real-dialogue smoke: `passed`.
- Capacity benchmark: `passed`.
- Backup/restore drill: `passed`.
- Dependency audit, SAST, frontend audit, and DAST baseline: `passed`.
- Production Compose config and production env guard: `passed`.

Cross-audit note:

- A previous report draft referenced the runtime-code commit
  `32290eef42f742db5121538059f7402a48019b58`. The cross-audit reran AI
  real-dialogue smoke and the full production acceptance probe while
  `1625841d8d527e6246cc17b47394afb20dbb9597` was HEAD; this report now records
  that accepted runtime evidence.
- The report file itself is committed after the acceptance run. That
  documentation commit changes the Git HEAD but not backend/frontend runtime
  image inputs. Later probe rechecks of this archived AI smoke report must pass
  `--ai-smoke-accepted-runtime-commit 1625841d8d527e6246cc17b47394afb20dbb9597`;
  the probe blocks reuse once guarded runtime/deploy paths have changed since
  the accepted runtime commit. Rerun the smoke/probe if a later commit changes
  runtime code, Compose, dependencies, migrations, frontend source, capacity
  plans, or deployment scripts.

## Probe Command

The final broad probe was run from `backend/` with:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --frontend-base-url http://localhost:5666 `
  --load-smoke-requests 32 `
  --load-smoke-concurrency 8 `
  --capacity-requests 64 `
  --capacity-concurrency 8 `
  --run-backup-restore-drill `
  --run-security-scans `
  --run-dast-baseline `
  --dast-target-url http://host.docker.internal:8000 `
  --ai-smoke-agent-id 59 `
  --ai-smoke-report ..\.trellis\tasks\05-10-conversation-2415-weather-routing\smoke-runs\20260510-current-head-cross-audit\report.raw.json `
  --ai-smoke-accepted-runtime-commit 1625841d8d527e6246cc17b47394afb20dbb9597 `
  --artifact-dir var\acceptance\20260510-current-head-cross-audit `
  --timeout 900 `
  --repo-root ..
```

## Evidence

Artifacts from the final run are under:

```text
var/acceptance/20260510-current-head-cross-audit/
```

The AI real-dialogue smoke report used by the probe is under:

```text
.trellis/tasks/05-10-conversation-2415-weather-routing/smoke-runs/20260510-current-head-cross-audit/report.raw.json
```

Important evidence points:

- API readiness: `/ready` passed.
- API health: `/health` passed.
- Metrics endpoint: `/metrics` passed.
- Frontend root: `http://localhost:5666/` passed.
- Capacity benchmark: Locust produced `1686` parsed measured requests, `0`
  failures, about `239 req/s`, and `p95=53ms` for `/ready`. This is
  repository-owned readiness evidence for the health endpoint, not a production
  business-workload capacity or SLO baseline.
- PostgreSQL restore drill: disposable restore database was created, restored,
  verified, and dropped; public table count was verified.
- Python dependency audit: `pip-audit` reported `0` known vulnerabilities across
  `187` dependencies.
- Python SAST: `bandit -ll` completed without a blocking failed result.
- Frontend dependency audit: full and production `pnpm audit` reported
  `high=0` and `critical=0`.
- DAST: OWASP ZAP baseline completed with no high/critical or fail-level
  alerts; remaining alerts were low or informational.
- AI smoke: strict real-dialogue report recorded `passed=3`, `failed=0`,
  `blocked=0`, with accepted runtime commit evidence and three live ASXS
  provider calls.
- Production Compose config: `docker compose --env-file ops\production.env.example
  -f docker-compose.prod.yml config --quiet` completed successfully.
- Production env guard: `docker compose --env-file <temporary-prod-shaped-env>
  -f docker-compose.prod.yml run --rm production-guard` printed
  `production env guard passed`.

## AI Runtime Fix Evidence

Recent release-blocking AI dialogue issues were covered by targeted regressions:

- Conversation `2415`: metadata-driven skill/tool routing now promotes
  executable tool families without hardcoding plugin-owned tool names in the
  main runtime.
- Conversation `2412`: knowledge-base status is prompt-visible and diagnostic
  when a bound-KB turn has no retrieved source; bound KB metadata is not treated
  as citation evidence.

Targeted checks run after the final fix:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\regressions\test_conversation_2412_kb_context_status.py tests\regressions\test_conversation_2412_kb_hybrid_keyword_fallback.py -q
```

Result:

```text
2 passed
```

Production probe path regression:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_production_acceptance_probe.py -q
```

Result:

```text
41 passed
```

## Release Decision

This runtime codebase is accepted as a release candidate for deployment into the
production environment, subject to environment-level checks during the release
window.

This report is not a replacement for operator signoff on the real production
host. It records that the repository-owned gates passed in the local acceptance
environment for the stated commit.

## Production Window Checks

Run these checks on the target deployment environment before opening traffic:

- Verify production `.env` values are real and not copied from
  `ops/production.env.example`.
- Verify TLS, public domain, tenant domain suffix, and reverse proxy settings.
- Verify PostgreSQL and Redis volumes are on production-grade persistent
  storage.
- Verify backup jobs and restore runbooks are enabled for the real database and
  storage volumes.
- Verify AI provider credentials and fallback providers are configured.
- Verify notification delivery channels, outbox processing, and queue workers.
- Verify monitoring, alert routes, and blackbox probes for `/ready`, `/health`,
  frontend, worker, beat, PostgreSQL, Redis, queue depth, and AI provider health.

## Known Operational Risks

These are not code blockers for this release candidate, but they should be
tracked during production rollout:

- The ASXS provider had intermittent timeout/connection failures during earlier
  smoke retries, even though the final smoke passed. Multi-provider production
  fallback depends on valid backup provider credentials.
- Deepseek and DashScope were not available in the local environment because
  production credentials were inactive or absent.
- ZAP still reported low/informational hardening notes such as security header
  recommendations. Public production ingress should add the expected response
  headers even though these did not block the baseline.
- The capacity benchmark was a readiness-target local benchmark against
  `/ready`, not a business-workload soak test. For high-traffic launch, run a
  longer environment-specific load plan with business endpoints and agreed SLOs.
