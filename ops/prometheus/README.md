# NovusAI Monitoring Acceptance Runbook

Date: 2026-05-08

## Scope

This runbook verifies the local development monitoring acceptance gate for the
NovusAI backend. It proves that the application exposes Prometheus metrics and
that a local Prometheus server can scrape the backend through the development
API port.

This does not replace a full production observability rollout. Capacity tests,
backup/restore drills, DAST, and AI real-dialogue smoke remain separate gates.

## Local Services

Start the shared local infrastructure and Prometheus from the repo root:

```powershell
docker compose -f docker-compose.dev.yml up -d postgres redis prometheus
```

Prometheus binds to `127.0.0.1:19090` by default because Windows commonly
reserves or blocks low monitoring ports such as `9090`. Override it only when
the host port is known to be available:

```powershell
$env:PROMETHEUS_HTTP_PORT = "19091"
docker compose -f docker-compose.dev.yml up -d prometheus
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

For a production Compose smoke stack, use `http://127.0.0.1:18000` when
probing the backend directly. If Prometheus should scrape the production
Compose API instead of the development API, point a dedicated smoke config at
`host.docker.internal:18000`; do not treat this development scrape config as a
production-stack default.

Verify the local Prometheus server:

```powershell
Invoke-WebRequest http://127.0.0.1:19090/-/ready -UseBasicParsing
Invoke-RestMethod "http://127.0.0.1:19090/api/v1/query?query=up%7Bjob%3D%22novusai-api%22%7D"
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

The DB and Redis component gauges are refreshed by `/ready`, `/health`, and the
`/metrics` scrape path. The scrape-time refresh is TTL-cached so Prometheus does
not force a database and Redis probe on every scrape while still avoiding stale
component-health samples when Prometheus is the only continuous caller.

For production, keep the TTL and scrape interval aligned. If the deployment uses
multiple workers, choose and document one aggregation strategy: single-worker
scrape, one target per worker, or Prometheus multiprocess mode. A blackbox
probe can still be added as an external alerting layer, but it is not required
for the in-process component gauges to refresh.

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

That probe result means the Prometheus exposition contract passed and the
scrape-time component refresh path is reachable. It still does not replace
production observability rollout, capacity testing, or external blackbox checks.

The overall report can still be `blocked` while load/capacity tooling,
backup/restore tooling, DAST tooling, and AI real-dialogue smoke prerequisites
are absent. Do not report those blocked gates as production-ready.
