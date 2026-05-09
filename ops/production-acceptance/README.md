# Production Acceptance Gates

This runbook records the executable local acceptance gates used before claiming
SaaS delivery readiness. The probe reports each gate as `passed`, `failed`, or
`blocked`.

## Command

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
  --artifact-dir ops\acceptance-artifacts `
  --allow-blocked `
  --timeout 5
```

When the target is the production Docker Compose smoke stack, pass the matching
PostgreSQL container and database identity from the compose environment, for
example:

```powershell
  --postgres-container novusai-prod-smoke-postgres-1 `
  --postgres-db novusai_saas `
  --postgres-user novusai
```

`--allow-blocked` only allows automation to exit 0 when no gate failed. It does
not convert blocked gates into passed gates. If any required provider
credential, agent selector, or archived real-dialogue report is missing, the
report's `overall_status` remains `blocked` and production acceptance must not
be claimed as passed.

## Latest Local Result

The previous 2026-05-09 local Compose run is no longer sufficient evidence
after the probe was hardened. Its capacity result used the built-in readiness
benchmark, and its archived AI smoke report was generated from an older dirty
worktree. Treat that artifact as historical only.

Current expected local status without fresh external evidence: `blocked`

Blocked gates:

- Capacity acceptance now requires a real k6/Locust/equivalent load plan. The
  built-in `/ready` load smoke remains useful, but it is not capacity
  acceptance.
- AI real-dialogue smoke reports must include repo evidence matching the current
  `git rev-parse HEAD` and must be generated from a clean worktree.

The archived real-dialogue report used for this run exists at
`.trellis/tasks/05-08-production-acceptance-gates/smoke-runs/20260509-ai-real-dialogue/report.json`
but it no longer satisfies the hardened current-commit smoke requirement.

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
  --allow-blocked
```

The older `python -m app.cli ai smoke` command remains useful as a runtime
capability/manifest check, but it is not a real-dialogue smoke because it does
not send a prompt through `AgentChatService` or prove a live provider call.

## Artifact Policy

Generated local artifacts live under `ops/acceptance-artifacts/` and are ignored
by Git. Regenerate them during release verification instead of treating one
developer machine's scan output as source. The probe writes security scan
artifacts such as `pip-audit.json`, `bandit.json`, `pnpm-audit-all.json`,
`pnpm-audit-prod.json`, and ZAP reports there. AI real-dialogue smoke raw
reports should be archived with the owning Trellis task under
`smoke-runs/<milestone>/` or uploaded as CI/release artifacts; do not use
`ops/acceptance-artifacts/` as the authoritative acceptance archive.

## Historical Plugin Backup Scope

Historical plugin backup packages under `backend/plugins/.backups/` are not part
of the new-system production delivery surface. They must not create skipped
release gates when the fixture files are absent. Supported plugin validation is
covered by the current plugin CLI, manifest, lifecycle, startup, package, and
runtime tests against active plugin contracts. If a historical backup plugin is
reintroduced as a supported package, restore it through the normal plugin source
tree and add current-contract tests instead of reviving backup-fixture
compatibility baselines.
