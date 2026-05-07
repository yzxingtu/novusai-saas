# NovusAI Monitoring Acceptance Runbook

Date: 2026-05-08

## Scope

This runbook verifies the local production-monitoring acceptance gate for the
NovusAI backend. It proves that the application exposes Prometheus metrics and
that a local Prometheus server can scrape the backend.

This does not replace a full production observability rollout. Capacity tests,
backup/restore drills, DAST, and AI real-dialogue smoke remain separate gates.

## Local Services

Start the shared local infrastructure and Prometheus from the repo root:

```powershell
docker compose -f docker-compose.dev.yml up -d postgres redis prometheus
```

Start the backend by the normal project flow, then verify direct application
metrics:

```powershell
Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing
```

Prometheus is configured by:

- `ops/prometheus/prometheus.dev.yml`
- `ops/prometheus/rules/novusai-dev.rules.yml`

Prometheus scrapes the host backend through:

```text
host.docker.internal:8000
```

Verify the local Prometheus server:

```powershell
Invoke-WebRequest http://localhost:9090/-/ready -UseBasicParsing
Invoke-RestMethod "http://localhost:9090/api/v1/query?query=up%7Bjob%3D%22novusai-api%22%7D"
```

## Backend Metrics Contract

The backend `/metrics` endpoint must return Prometheus text exposition, not the
project JSON response envelope. The production acceptance probe expects these
metric families:

- `novusai_app_info`
- `novusai_http_requests_total`
- `novusai_http_request_duration_seconds`
- `novusai_http_requests_in_progress`
- `novusai_component_health`

Request metrics use low-cardinality labels only:

- `method`
- `route`
- `status_code`

Do not add tenant, user, trace, query, raw path, or host labels to these shared
HTTP metrics.

## Alert Rules

The local rule file provides baseline acceptance alerts:

- backend metrics scrape down
- HTTP 5xx rate above 5%
- HTTP P95 latency above 1 second
- database readiness unhealthy
- Redis health degraded

The DB and Redis component gauges are updated by `/ready` and `/health`. For
this local acceptance flow, the production probe calls `/ready` and `/health`
before `/metrics`, so those component gauges are refreshed before the scrape
assertion. A production deployment must add a continuous health prober,
blackbox exporter, or in-process refresh strategy before treating these
component gauges as self-sustaining DB/Redis alerts under Prometheus-only
scraping.

## Production Acceptance Probe

Run from `backend/`:

```powershell
.\.venv\Scripts\python.exe scripts\production_acceptance_probe.py `
  --api-base-url http://localhost:8000 `
  --frontend-base-url http://localhost:5666 `
  --load-smoke-requests 32 `
  --load-smoke-concurrency 8 `
  --allow-blocked
```

Expected monitoring result after this task:

```text
prometheus_metrics_endpoint: passed
```

The overall report can still be `blocked` while load/capacity tooling,
backup/restore tooling, DAST tooling, and AI real-dialogue smoke prerequisites
are absent. Do not report those blocked gates as production-ready.
