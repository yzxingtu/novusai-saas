# Production Acceptance Gates

This runbook records the executable local acceptance gates used before claiming
SaaS delivery readiness. The probe reports each gate as `passed`, `failed`, or
`blocked`.

## Local Development Stack Command

Run from `backend/` while the local API, frontend, PostgreSQL, Redis, and Docker
are available:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --frontend-base-url http://localhost:5666 `
  --load-smoke-requests 32 `
  --load-smoke-concurrency 8 `
  --capacity-requests 96 `
  --capacity-concurrency 16 `
  --capacity-p95-budget-ms 1500 `
  --capacity-error-budget-ratio 0 `
  --run-backup-restore-drill `
  --run-security-scans `
  --run-dast-baseline `
  --dast-target-url http://localhost:8000 `
  --ai-smoke-agent-id <id> `
  --ai-smoke-report ..\.trellis\tasks\05-08-production-acceptance-gates\smoke-runs\<run-id>\report.json `
  --ai-smoke-accepted-runtime-commit <accepted-runtime-commit> `
  --artifact-dir ops\acceptance-artifacts `
  --allow-blocked `
  --timeout 5
```

The command above targets the local development stack: backend on `8000` and
frontend on `5666`.

## Production Compose Smoke Command

When the target is the production Docker Compose smoke stack, target the
production compose host ports and pass the matching PostgreSQL container and
database identity from the compose environment. `docker-compose.prod.yml`
sets the Compose project name to `novusai-prod`, so the default PostgreSQL
container is `novusai-prod-postgres-1`. If an operator starts the stack with
`docker compose -p <project>`, use `<project>-postgres-1` instead.

The production Compose file consumes immutable prebuilt images through
`NOVUSAI_IMAGE_TAG`. It intentionally contains no `build:` sections, so a
production smoke cannot silently rebuild local source into the release stack.

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://127.0.0.1:18000 `
  --frontend-base-url http://127.0.0.1:18080 `
  --load-smoke-requests 32 `
  --load-smoke-concurrency 8 `
  --capacity-requests 96 `
  --capacity-concurrency 16 `
  --capacity-p95-budget-ms 1500 `
  --capacity-error-budget-ratio 0 `
  --run-backup-restore-drill `
  --run-security-scans `
  --run-dast-baseline `
  --dast-target-url http://127.0.0.1:18000 `
  --postgres-container novusai-prod-postgres-1 `
  --postgres-db novusai_saas `
  --postgres-user novusai `
  --ai-smoke-agent-id <id> `
  --ai-smoke-report ..\.trellis\tasks\05-08-production-acceptance-gates\smoke-runs\<run-id>\report.json `
  --ai-smoke-accepted-runtime-commit <accepted-runtime-commit> `
  --artifact-dir ops\acceptance-artifacts `
  --allow-blocked `
  --timeout 5
```

`--allow-blocked` only allows automation to exit 0 when no gate failed. It does
not convert blocked gates into passed gates. If any required provider
credential, agent selector, or archived real-dialogue report is missing, the
report's `overall_status` remains `blocked` and production acceptance must not
be claimed as passed.

## Latest Local Result

The latest accepted local release-candidate evidence is recorded in:

```text
ops/production-acceptance/20260510-release-readiness.md
```

Status for accepted runtime commit `1625841d8d527e6246cc17b47394afb20dbb9597`:

- `overall_status=passed`
- `23 passed / 0 failed / 0 blocked`
- AI real-dialogue smoke report matched the accepted runtime commit through
  `--ai-smoke-accepted-runtime-commit` and recorded `repo.dirty=false`.
- Capacity acceptance used the checked-in Locust plan and produced parseable
  metrics.
- The report itself may be committed after the accepted runtime commit; pass
  `--ai-smoke-accepted-runtime-commit 1625841d8d527e6246cc17b47394afb20dbb9597`
  when rechecking that accepted report from a later documentation/evidence
  commit. The probe rejects this reuse when guarded runtime/deploy paths have
  changed since the accepted runtime commit. Rerun the smoke/probe when runtime
  code, Compose, dependencies, migrations, frontend source, capacity plans, or
  deployment scripts change.

Older 2026-05-09 local Compose artifacts are historical only because the probe
was later hardened to require current-commit AI smoke evidence and checked-in
capacity runner output.

## AI Real-Dialogue Smoke

The probe intentionally does not mark AI dialogue production acceptance as
passed without real external evidence. To clear the remaining blocked gates:

1. Configure a real provider credential through runtime provider config,
   `backend/.env`, or the process environment.
2. Configure `AI_SMOKE_AGENT_ID` or `AI_SMOKE_AGENT_CODE`.
3. Run the AI real-dialogue smoke command against the scenarios in
   `.trellis/tasks/04-23-codex-llm-first-dialogue-replan/smoke-scenarios.md`.
4. Archive the strict JSON report with `schema_version:
   ai-real-dialogue-smoke/v1`, `report_type: ai_real_dialogue_smoke`,
   `execution_kind: real_dialogue`, `overall_status: passed`, matching ledger
   hash, provider call evidence, `provider.call_logs`, and per-scenario
   `conversation_id`, `provider_call_log_id`, observable checks, and pass/fail
   results. Then pass the report path to the probe with `--ai-smoke-report`.
   If later documentation or evidence commits move HEAD beyond the runtime
   commit that produced the report, also pass
   `--ai-smoke-accepted-runtime-commit <commit>`. The probe still rejects a
   report whose `repo.dirty` is not exactly `false`, and it blocks accepted
   runtime reuse when guarded runtime/deploy paths changed after that commit.

Example:

```powershell
$smokeDir = "..\.trellis\tasks\05-08-production-acceptance-gates\smoke-runs\<milestone>"
New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null

.\.venv\Scripts\python.exe -m app.cli ai real-dialogue-smoke --agent-id <id> --raw-json `
  > "$smokeDir\report.json"

.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --frontend-base-url http://localhost:5666 `
  --ai-smoke-agent-id <id> `
  --ai-smoke-report "$smokeDir\report.json" `
  --ai-smoke-accepted-runtime-commit <accepted-runtime-commit> `
  --allow-blocked
```

The older `python -m app.cli ai smoke` command remains useful as a runtime
capability/manifest check, but it is not a real-dialogue smoke because it does
not send a prompt through `AgentChatService` or prove a live provider call.

## Capacity Benchmark

Capacity acceptance is a real runner gate, separate from the lightweight
Python `/ready` load smoke. The canonical checked-in plans are:

- `ops/production-acceptance/capacity/locust_ready.py`
- `ops/production-acceptance/capacity/k6_ready.js`

The probe prefers Locust when the Python module or `locust` binary is available
and falls back to `k6` when only `k6` is installed. The benchmark targets
`GET /ready`, validates `200` plus `data.ready=true`, writes artifacts under
`ops/acceptance-artifacts/capacity/`, and parses the runner output before
classifying the gate.

Local readiness runner target. `--capacity-requests` is the minimum completed
request count required by the probe, not a hard stop for the runner. These
values prove that the checked-in `/ready` runner can execute and stay within
the configured thresholds on the tested machine; they are not a production
traffic baseline, a business-workload soak test, or an SLO claim:

- `--capacity-requests 96`
- `--capacity-concurrency 16`
- `--capacity-p95-budget-ms 1500`
- `--capacity-error-budget-ratio 0`

The 2026-05-10 release-readiness run used the same `/ready` gate with
`--capacity-requests 64` and `--capacity-concurrency 8`; that result is
accepted only as repository-owned local readiness evidence for the stated
runtime commit.

Pass / fail / blocked rules:

- `passed`: a checked-in Locust or k6 plan ran against the target stack,
  produced parseable metrics, completed at least the requested count, stayed
  within the p95 budget, and stayed within the error budget.
- `failed`: the runner produced metrics but p95, error ratio, semantic checks,
  runner exit status, or completed request count breached the configured
  thresholds.
- `blocked`: Locust/k6 is absent, the target stack is unavailable, the plan file
  is missing, or the runner could not produce parseable artifacts.

Reproducible direct Locust command:

```powershell
cd <repo-root>
$env:CAPACITY_TARGET_PATH = "/ready"

.\backend\.venv\Scripts\python.exe -m locust `
  -f ops\production-acceptance\capacity\locust_ready.py `
  --headless `
  -u 16 `
  -r 16 `
  --host http://localhost:8000 `
  --run-time 5s `
  --csv ops\acceptance-artifacts\capacity\manual-locust `
  --only-summary
```

For the production compose smoke stack, replace the Locust host with
`http://127.0.0.1:18000`.

Reproducible direct k6 command:

```powershell
cd <repo-root>
$env:API_BASE_URL = "http://localhost:8000"
$env:CAPACITY_TARGET_PATH = "/ready"

k6 run `
  --vus 16 `
  --iterations 96 `
  --summary-export ops\acceptance-artifacts\capacity\manual-k6-summary.json `
  ops\production-acceptance\capacity\k6_ready.js
```

For the production compose smoke stack, set `$env:API_BASE_URL` to
`http://127.0.0.1:18000`.

## Artifact Policy

Generated local artifacts live under `ops/acceptance-artifacts/` and are ignored
by Git. Regenerate them during release verification instead of treating one
developer machine's scan output as source. The probe writes security scan
artifacts such as `pip-audit.json`, `bandit.json`, `pnpm-audit-all.json`,
`pnpm-audit-prod.json`, and ZAP reports there. AI real-dialogue smoke raw
reports should be archived with the owning Trellis task under
`smoke-runs/<milestone>/` or uploaded as CI/release artifacts; do not use
`ops/acceptance-artifacts/` as the authoritative acceptance archive.

`pip-audit` is retried once when the command output indicates transient network,
TLS, proxy, or remote service unavailability. Each attempt writes separate
stdout/stderr logs and an attempt JSON path under the artifact directory; the
canonical `pip-audit.json` is refreshed only from the current run. Network-only
exhaustion remains `blocked`, while a parseable vulnerability result remains
`failed` and is not retried into a softer status.

## Historical Plugin Backup Scope

Historical plugin backup packages under `backend/plugins/.backups/` are not part
of the new-system production delivery surface. They must not create skipped
release gates when the fixture files are absent. Supported plugin validation is
covered by the current plugin CLI, manifest, lifecycle, startup, package, and
runtime tests against active plugin contracts. If a historical backup plugin is
reintroduced as a supported package, restore it through the normal plugin source
tree and add current-contract tests instead of reviving backup-fixture
compatibility baselines.
