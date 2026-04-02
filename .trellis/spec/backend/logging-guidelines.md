# Logging Guidelines

> Logging in NovusAI SaaS is trace-first. Every meaningful operational event
> should be diagnosable through `X-Trace-ID` and the unified logging facade.

## Overview

- Use `backend/app/core/logging.py` as the only supported logging facade.
- Preferred entrypoints:
  - `get_logger(__name__)`
  - `LoggerMixin` and category-specific mixins
- Trace ids are injected automatically by the Loguru patcher from
  `trace_id_var`.

Examples:

- Logging facade: `backend/app/core/logging.py`
- Trace middleware: `backend/app/middleware/trace.py`
- Main app logger usage: `backend/app/main.py`

## Log Levels

- `DEBUG`: local diagnostics only, avoid leaving noisy debug logs in hot paths.
- `INFO`: workflow milestones and expected operational events.
- `WARNING`: degraded but recoverable situations.
- `ERROR`: failed user or system operations that need attention.
- `CRITICAL`: severe system failures.

Use structured logger calls with `{}` placeholders, not `%s` / `%d`.

## Structured Logging

- `TraceIdMiddleware` reads or generates `X-Trace-ID`.
- The trace id is written to request state, context var, and response headers.
- Ordinary logs receive the trace id automatically through the patcher.
- Standard production/debug lookup entrypoint is `novusai trace show <trace_id>`.
- Treat `novusai trace show <trace_id>` as the normal operator workflow before
  manual log digging; production-oriented output is redacted by default.

Primary references:

- `backend/app/middleware/trace.py`
- `backend/app/core/logging.py`
- `.cursor/rules/trace-and-monitoring.md`

## What to Log

- Entry/exit points for operationally significant workflows.
- Errors with enough context to debug using trace id.
- Queue/task lifecycle events.
- Storage, auth, captcha, and impersonation events through their existing
  categories.
- AI health, audit, or worker logging when it affects operator visibility.
- Notification and websocket events should keep using the established service
  and bridge entrypoints instead of ad-hoc emission code.

Examples:

- Task lifecycle logging: `backend/app/tasks/ai.py`
- Tenant/plugin logging: `backend/app/api/tenant/plugins.py`
- Shared helper logger: `backend/app/api/shared/_kb_helpers.py`
- Notification service: `backend/app/services/common/notification_service.py`

## What NOT to Log

- Secrets, tokens, raw passwords, or unredacted credentials.
- Hand-built duplicated trace metadata when the shared logger already injects
  it.
- Extremely noisy handshake logs unless the subsystem explicitly needs them.
- Giant raw payload dumps when truncation/sanitization helpers already exist.

Example:

- AI request sanitization and response truncation: `backend/app/tasks/ai.py`

## Logger Categories And Sync Contexts

- The repo already separates logs into categories such as `app`, `error`, `db`,
  `task`, `queue`, `captcha`, `storage`, `auth`, and `impersonate`.
- Business tasks must use `@register_task`.
- Task functions should accept `self` first, use sync DB/session patterns, and
  return JSON-serializable results.
- Common task queues include `default`, `high_priority`, `ai_gateway`,
  `scheduled`, and `notification`.
- Workers are synchronous; use `BaseTask` / `TenantTask` or
  `sync_session_factory()` where appropriate.
- Do not implement a second trace propagation mechanism for Celery.
- For Socket.IO from sync contexts, use the bridge helpers instead of async
  emit calls directly.
- Notification delivery should continue to flow through `NotificationService`
  rather than ad-hoc mail or socket writes in business code.
- Socket.IO namespaces are fixed to `/admin`, `/tenant`, and `/user`; common
  room conventions include `user:{user_id}`, `tenant:{tenant_id}`, and `admins`.
- New task modules must be reachable from Celery include/import wiring.

Examples:

- `backend/app/core/logging.py`
- `backend/app/tasks/base.py`
- `backend/app/tasks/ai.py`
- `backend/app/celery_app.py`
- `backend/app/sio/admin_ns.py`
- `backend/app/core/sio_bridge.py`
- `backend/app/services/common/notification_service.py`

## Monitoring Notes

- Current observability is log and trace centric, not a centralized
  metrics-only stack.
- Existing monitoring surfaces include system logs, AI health, and presence
  endpoints.
- Do not assume there is a central `metrics.py`.
- If Prometheus-style metrics are added, define them beside the owning module
  and guard them defensively.

## Anti-Patterns

- `print()` for debugging in request, task, or plugin code.
- `logging.getLogger()` or raw `loguru.logger` in business modules.
- Rebuilding `trace_id` formatting by hand when the shared patcher already adds
  it.
- Logging secrets or unredacted credentials.
- Emitting async Socket.IO calls from sync Celery contexts instead of the bridge
  helpers.
