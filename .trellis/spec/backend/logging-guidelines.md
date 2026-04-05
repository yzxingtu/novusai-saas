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

## Scenario: Immutable Identity Snapshots For Audit And AI Logs

### 1. Scope / Trigger

- Trigger: any change that writes or serializes operator / caller / actor
  identity in operation logs, AI action logs, AI call logs, or monitoring
  aggregations.
- Why this needs code-spec depth: historical audit entries must stay tied to the
  identity state at write time even after nickname, avatar, org node, or role
  changes.

### 2. Signatures

- DB columns:
  - `backend/app/models/system/operation_log.py` -> `OperationLog.identity_snapshot`
  - `backend/app/models/ai/action_log.py` -> `AIActionLog.operator_snapshot`
- Snapshot helpers:
  - `backend/app/core/identity_snapshot.py`
  - `build_identity_snapshot(...)`
  - `load_identity_snapshot(db, *, user_type, user_id, tenant_id, fallback_username, fallback_nickname)`
- Write paths:
  - `backend/app/services/system/operation_log_service.py`
  - `backend/app/services/ai/action_log_service.py`
  - `backend/app/services/ai/call_log_service.py`
  - `backend/app/tasks/ai.py`
- Read / aggregation paths:
  - `backend/app/schemas/system/operation_log.py`
  - `backend/app/repositories/ai/call_log_repository.py`
  - `backend/app/services/ai/monitoring_service.py`

### 3. Contracts

- Snapshot payload must prefer immutable display fields:
  - `display_name`
  - `username`
  - `nickname`
  - `avatar`
  - `org_node_id`
  - `org_node_name`
  - `role_name`
  - `display_role_name`
  - `user_type`
  - `is_active`
  - `is_owner`
  - `is_leader`
- `operation_logs.identity_snapshot` stores the actor snapshot for system audit
  rows.
- `ai_action_logs.operator_snapshot` stores the operator snapshot for AI action
  audit rows.
- `ai_call_logs.request_metadata.caller_snapshot` stores the caller snapshot for
  usage / monitoring records.
- Serialization rule: snapshot-first, live-identity fallback. Read paths must
  use snapshot values when a snapshot key is present, even if the current user
  profile has since changed.
- Fallback rule: if a snapshot is absent, incomplete, or belongs to a deleted
  actor, use live identity data when available and finally fall back to stored
  username / nickname / id placeholders.

### 4. Validation & Error Matrix

| Condition | Expected Behavior |
|---|---|
| Snapshot column / metadata exists and contains field | Use snapshot value |
| Snapshot absent but live actor exists | Use live actor data |
| Snapshot absent and live actor missing | Use stored username / nickname fallback |
| Actor renamed or moved org after log write | Historical row still shows old snapshot |
| Async operation log write has `user_id` but no snapshot yet | `load_identity_snapshot()` fills snapshot before insert |
| AI call written through Celery task | `tasks/ai.py` must pass `caller_snapshot` into `request_metadata` |

### 5. Good/Base/Bad Cases

- Good: `OperationLog.identity_snapshot.org_node_name = "平台管理组"` and the
  admin later moves elsewhere; the log still renders `平台管理组`.
- Base: a low-context log row only has `username` / `nickname`; serializer falls
  back cleanly without throwing.
- Bad: list / detail code ignores snapshot keys and always joins the current
  admin / tenant tables, causing history to drift after profile edits.

### 6. Tests Required

- `backend/tests/services/test_operation_log_service.py`
  - asserts async operation-log writes populate `identity_snapshot`
  - asserts serializer prefers snapshot display fields
- `backend/tests/services/test_ai_action_log_service.py`
  - asserts operator snapshot fields override live operator data on read
- `backend/tests/services/test_call_log_service.py`
  - asserts call-log write path keeps `caller_snapshot`
- `backend/tests/services/test_call_log_repository.py`
  - asserts repository list/detail uses `caller_snapshot` before live actor joins
- `backend/tests/services/test_monitoring_service.py`
  - asserts monitoring actor cards use call-log snapshot-first behavior

### 7. Wrong vs Correct

#### Wrong

- Write only `user_id` and fetch nickname / org / role from the current user
  table every time a log is rendered.
- Treat missing snapshot as an error instead of falling back safely.

#### Correct

- Capture identity display fields at write time with
  `build_identity_snapshot()` / `load_identity_snapshot()`.
- In read paths, check `snapshot_has_key()` / `snapshot_value()` first and only
  then merge live identity data.

## Anti-Patterns

- `print()` for debugging in request, task, or plugin code.
- `logging.getLogger()` or raw `loguru.logger` in business modules.
- Rebuilding `trace_id` formatting by hand when the shared patcher already adds
  it.
- Logging secrets or unredacted credentials.
- Emitting async Socket.IO calls from sync Celery contexts instead of the bridge
  helpers.
