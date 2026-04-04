# Backend Development Guidelines

> Actual backend conventions for NovusAI SaaS. These guidelines are distilled
> from `.cursor/rules/*.md`, `.cursor/skills/novusai-saas/references/*.md`,
> and the current FastAPI codebase.

## Stack Summary

- Python 3.10+ with FastAPI, SQLAlchemy 2.x async, PostgreSQL, Redis, Celery,
  Alembic, and Socket.IO.
- Three API surfaces are maintained separately: `admin`, `tenant`, and `user`.
- The standard request path is `Middleware -> Controller -> Service ->
  Repository -> Model/DB`.
- Tenant-aware features must use the tenant base classes; platform-wide
  features must use global base classes.

## Sources Of Truth

- Core controller hierarchy: `backend/app/core/base_controller.py`
- Unified responses and public error text: `backend/app/core/response.py`
- Trace propagation: `backend/app/middleware/trace.py`
- Logging facade: `backend/app/core/logging.py`
- Model export and Alembic registration:
  `backend/app/models/__init__.py`, `backend/migrations/env.py`
- Representative CRUD chain:
  - `backend/app/models/tenant/tenant_domain.py`
  - `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
  - `backend/app/services/system/tenant_domain_service.py`
  - `backend/app/api/tenant/domains.py`

## Guidelines Index

| Guide | Description | When to Read |
|-------|-------------|--------------|
| [Directory Structure](./directory-structure.md) | Where controllers, services, repositories, models, schemas, tasks, and plugin code live | Before adding or moving files |
| [Database Guidelines](./database-guidelines.md) | Model design, repository rules, JSON:API filters, and Alembic conventions | Before schema, query, or migration work |
| [Error Handling](./error-handling.md) | How to raise, localize, and return errors without breaking traceability | Before controller or service changes |
| [Logging Guidelines](./logging-guidelines.md) | Trace-aware logging, categories, and operational debugging rules | Before adding logs, Celery work, or monitoring code |
| [Quality Guidelines](./quality-guidelines.md) | Tests, linting, review bar, and mandatory validation paths | Before merging backend work |

## Non-Negotiable Rules

- Do not put business logic in controllers.
- Do not query the database directly from controllers.
- Do not put repository responsibilities into services.
- Do not return ad-hoc dict shapes; use `success()`, `created()`, `paginated()`,
  `deleted()`, or `error()`.
- Do not use `print()`, `logging.getLogger()`, or raw `loguru.logger`; use
  `app.core.logging`.
- Do not hardcode user-facing text; backend strings must go through `_()`.
- Do not hardcode fixed LLM-facing prompts, tool descriptions, or model
  instruction blocks directly in Python business/runtime code; store them under
  `backend/app/ai/prompt_contracts/resources/` and load them through the shared
  prompt contract renderer.
- Do not add new handwritten models without exporting them from
  `backend/app/models/__init__.py` and registering them in
  `backend/migrations/env.py`.
- Do not write migration SQL with f-string identifiers or `text(f"...")`.
- Do not hand-call `.isoformat()` on model datetimes in API payloads unless you
  also normalize naive UTC values to `+00:00`; prefer returning raw `datetime`
  objects through `success()` / `paginated()` or using
  `serialize_datetime_for_api()`.
- Do not write `utc_now()` into `DateTime(timezone=True)` columns; use an aware
  UTC value such as `datetime.now(timezone.utc)` for timestamptz fields.

## Pre-Development Checklist

Read these files in order when touching backend code:

1. This index.
2. [Directory Structure](./directory-structure.md)
3. The task-specific file:
   - schema or repository work -> [Database Guidelines](./database-guidelines.md)
   - controller/service exceptions -> [Error Handling](./error-handling.md)
   - logs, trace, tasks, monitoring -> [Logging Guidelines](./logging-guidelines.md)
   - tests or release readiness -> [Quality Guidelines](./quality-guidelines.md)
   - AI runtime / routing / prompt contract work -> also inspect
     `backend/app/ai/prompt_contracts/` before adding or changing any fixed
     model-facing instruction text
4. If the task crosses frontend, AI, plugins, uploads, or domains, also read
   `../guides/cross-layer-thinking-guide.md`.

## Representative Examples In This Repo

- Tenant-scoped controller with RBAC and menu metadata:
  `backend/app/api/tenant/domains.py`
- Tenant model with `__filterable__`, `__sortable__`, `__selectable__`, and
  delete dependencies: `backend/app/models/tenant/tenant_domain.py`
- Tenant repository extending `TenantRepository`:
  `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
- Global service coordinating quota checks and domain lifecycle:
  `backend/app/services/system/tenant_domain_service.py`
- Celery task registered with `@register_task` and sync DB session usage:
  `backend/app/tasks/ai.py`

## Anti-Patterns To Avoid

- Copying a pattern from another codebase that bypasses the NovusAI base
  classes.
- Adding a "quick" raw SQL path in a service instead of extending a repository.
- Swallowing exceptions with `except Exception: pass` or `continue`.
- Expanding legacy `200 + success=false` response shapes into new APIs.
- Re-implementing trace propagation or log formatting manually.
- Writing or editing fixed model-facing prompt text inline in Python instead of
  using the shared prompt contract resources.
