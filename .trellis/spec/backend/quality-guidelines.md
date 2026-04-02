# Quality Guidelines

> Backend changes are not done when the code compiles. They are done when the
> relevant tests, contracts, and operational checks are covered.

## Overview

Required commands from `backend/`:

```bash
pytest
ruff check .
ruff format .
```

Primary references:

- `backend/pyproject.toml`
- `README.md`

## Forbidden Patterns

- Controller logic that performs business decisions or direct DB queries.
- Service logic that manually reconstructs repository behavior.
- `except Exception: pass` or `continue`.
- New raw `@celery_app.task` or `@shared_task` in business task modules.
- New migration SQL using interpolated identifiers.
- Shipping backend work without the tests that already exist for the touched
  subsystem.
- Reintroducing deprecated AI runtime paths such as `ToolRegistry` or
  `tool_bindings`.

## Required Patterns

- New or substantially changed services should have unit tests in
  `backend/tests/services/`.
- Tests must not depend on a real database, Redis, network, or third-party API.
- Reuse fixtures and mock factories from `backend/tests/services/conftest.py`.
- Many service tests instantiate services with `__new__` and inject `db`,
  `tenant_id`, and `repo` manually; follow that existing pattern.
- Async service tests should use `pytest.mark.asyncio`.
- For uploads, quotas, traces, plugins, and domain isolation, include at least
  one real-path validation step in addition to unit tests.
- New RBAC-aware controllers should update `@permission_resource`,
  `parent_resource`, and the matching `messages.json` action translations in the
  same change.
- Plugin permission changes should continue to use
  `sync_plugin_permissions(plugin.name)` instead of broad ad-hoc refreshes.
- Row-level permission changes should be validated through the repository/base
  filtering path, not only through service mocks.
- New code comments, docstrings, `TODO`, or `FIXME` notes should follow the
  repo's bilingual comment convention when comments are necessary.

Examples:

- `backend/tests/services/conftest.py`
- `backend/tests/services/test_attachment_service.py`
- `backend/tests/services/test_ai_quota_runtime_diagnostics.py`

## Testing Requirements

### Service changes

- Cover happy path, boundary conditions, and failure branches.
- Prefer multiple focused cases over one oversized integration test.

### Upload, visibility, and storage work

- Run targeted attachment/storage tests.
- Validate visibility-sensitive behavior, not only upload success.
- Prefer browser validation with chrome-devtools first; use Playwright when file
  upload or multi-tab behavior makes it necessary.

Examples:

- `backend/tests/services/test_attachment_service.py`
- `backend/tests/test_storage_plugins.py`

### Trace, error, and logging work

- Verify user-visible errors preserve `trace_id`.
- Verify `novusai trace show <trace_id>` remains a usable operator entrypoint.
- If the change affects frontend-visible failures, confirm the UI still shows
  one coherent error path rather than duplicate toasts.
- For AI streaming fallback fixes, validate both "upstream fails before first
  chunk" and "stream returns no meaningful chunk" scenarios so the user never
  receives a silent empty assistant turn.

### AI quota, rate limit, or AI logging work

- Do not stop after lint or type checks.
- Validate runtime behavior, queue consumption, and diagnostics fields where
  relevant.
- When AI call logging or task signatures change, verify the worker is running
  the new code and consuming the `ai_gateway` queue.
- If the UI depends on those logs or limits, validate the full operator path,
  not just the backend return payload.

### Recycle bin and route-order work

- For recycle-bin-enabled modules, validate the module recycle bin flow and the
  surface-specific route behavior.
- If a controller has dynamic `/{id}` style routes, confirm recycle-bin routes
  are registered early enough to avoid path-parameter collisions.

## Code Review Checklist

Before merge, confirm:

- The code lives in the correct layer.
- Tenant vs global scope is correct.
- Admin, tenant, and user surface boundaries remain intact.
- i18n, permission, menu, trace, migration, and tests are updated together when
  required.
- Controllers are thin and services carry business logic.
- Repositories own data access.
- Any new model is exported and migration-registered.
- Any new task is registered with `@register_task` and reachable by the worker.

## Real Examples To Follow

- Service/unit-test style:
  - `backend/tests/services/test_attachment_service.py`
  - `backend/tests/services/test_agent_service.py`
- Trace/log aware task implementation:
  - `backend/app/tasks/ai.py`
- Layered tenant CRUD:
  - `backend/app/api/tenant/domains.py`
  - `backend/app/services/system/tenant_domain_service.py`
  - `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
