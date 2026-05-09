# NovusAI Production Deployment Runbook

Date: 2026-05-09

## Scope

This runbook covers the repo-owned Docker and Docker Compose production entry.
It verifies image build inputs, the production environment guard, one-shot
database migrations, API readiness, Celery worker/beat startup, and the frontend
nginx container.

This is not a full production acceptance signoff. Capacity, backup/restore,
security scan, DAST, monitoring, and AI real-dialogue smoke gates remain covered
by `ops/production-acceptance/README.md` and
`docs/operations/production-acceptance-runbook.md`.

## Environment File

Copy `ops/production.env.example` to a private path outside the repository and
replace every placeholder. The copied file must set `NOVUSAI_PROD_ENV_FILE` to
that same private path because Compose uses it twice:

- `--env-file <prod.env>` supplies interpolation values while Compose reads the
  YAML.
- `NOVUSAI_PROD_ENV_FILE=<prod.env>` supplies the service `env_file` path used
  inside the compose model.

Use an immutable release tag. Do not use `latest`, `dev`, `test`, or example
values:

```powershell
$envFile = "C:\secure\novusai-prod.env"
docker compose --env-file $envFile -f docker-compose.prod.yml config --quiet
docker compose --env-file $envFile -f docker-compose.prod.yml run --rm production-guard
```

The checked-in example is intentionally rejected by `production-guard`.

## Build

Backend image targets are built from the `backend/` context:

```powershell
docker build -f backend/Dockerfile --target api backend
docker build -f backend/Dockerfile --target worker backend
docker build -f backend/Dockerfile --target beat backend
```

The frontend Dockerfile must be built from the repository root because it copies
both `frontend/` and the backend plugin metadata used by the Vite plugin
discovery step:

```powershell
docker build -f frontend/scripts/deploy/Dockerfile . `
  --build-arg VITE_GLOB_API_URL=https://api.your-production-domain.tld `
  --build-arg VITE_PLATFORM_DOMAINS=app.your-production-domain.tld `
  --build-arg VITE_APP_NAMESPACE=novusai-web-saas `
  --build-arg VITE_APP_STORE_SECURE_KEY=<real-high-entropy-client-storage-key>
```

Do not use `docker build -f frontend/scripts/deploy/Dockerfile frontend`; that
context cannot contain `backend/app` and `backend/plugins`, so the build will
fail.

For local frontend image builds through the helper script, export the same build
args first:

```bash
export VITE_GLOB_API_URL=https://api.your-production-domain.tld
export VITE_PLATFORM_DOMAINS=app.your-production-domain.tld
export VITE_APP_STORE_SECURE_KEY=<real-high-entropy-client-storage-key>
cd frontend
./scripts/deploy/build-local-docker-image.sh
```

## Compose Startup

For a release host that already has immutable images, prefer `--no-build`.
For a local clean-room verification, `--build` is acceptable.

```powershell
$envFile = "C:\secure\novusai-prod.env"
docker compose --env-file $envFile -f docker-compose.prod.yml up -d --build --wait
```

The production compose graph starts in this order:

- `production-guard` validates required production env values and refuses the
  checked-in example.
- `postgres` and password-protected `redis` become healthy.
- `backend-migrate` runs `novusai db upgrade heads` once and must exit `0`.
- `backend-api`, `backend-worker`, and `backend-beat` start only after the
  migration container completes successfully.
- `frontend` starts after the API healthcheck passes.

## Migration Strategy

Production compose sets `RUN_MIGRATIONS_ON_STARTUP=false` for backend runtime
containers. The API verifies database connectivity on startup but does not run
Alembic. Schema changes are owned by the one-shot `backend-migrate` service:

```powershell
docker compose --env-file $envFile -f docker-compose.prod.yml up backend-migrate
docker compose --env-file $envFile -f docker-compose.prod.yml logs backend-migrate
```

Do not bypass this with API startup migrations in production.

## Health Checks

After startup, verify the runtime surface:

```powershell
docker compose --env-file $envFile -f docker-compose.prod.yml ps -a
Invoke-RestMethod http://127.0.0.1:<BACKEND_HTTP_PORT>/ready
Invoke-RestMethod http://127.0.0.1:<BACKEND_HTTP_PORT>/health
Invoke-WebRequest http://127.0.0.1:<FRONTEND_HTTP_PORT>/ -UseBasicParsing
docker compose --env-file $envFile -f docker-compose.prod.yml exec -T backend-worker `
  python -m celery -A app.celery_app:celery_app inspect ping --timeout=5
docker compose --env-file $envFile -f docker-compose.prod.yml exec -T backend-beat `
  sh -lc "test -w /app/var/celerybeat && ls -la /app/var/celerybeat && novusai check celery"
```

Expected results:

- `/ready` returns `ready=true` with database and Redis `ok`.
- `/health` returns `status=healthy`.
- Frontend returns HTTP 200 and an HTML app shell.
- Worker inspect reports one or more Celery nodes online.
- Beat has a writable `/app/var/celerybeat` schedule directory and can reach the
  Celery broker.

## Production Limitations

This compose file is a repo-owned single-host deployment entry, not a complete
high-availability platform design.

- Use an external TLS reverse proxy, ingress, load balancer, or platform network
  policy for public exposure.
- Back up PostgreSQL and storage volumes outside Compose and run restore drills
  before release acceptance.
- Keep `backend_storage`, `backend_logs`, `backend_beat_state`, `postgres_data`,
  and `redis_data` on production-grade persistent storage.
- The frontend `VITE_*` values are compiled into static assets. Treat
  `VITE_APP_STORE_SECURE_KEY` as a build-time public configuration value, not as
  a server-side secret.
- If custom domains are enabled, set a real `TENANT_DOMAIN_SUFFIX`,
  `ACME_ACCOUNT_EMAIL`, and `SSL_PRIVATE_KEY_ENCRYPTION_KEY`.
- Do not claim full production readiness until the acceptance runbook gates are
  green or explicitly recorded as blocked with owner follow-up.
