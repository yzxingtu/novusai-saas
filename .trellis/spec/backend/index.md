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
- Controller-local helper classes inside `app/api/**` still count as controller
  logic. If a route needs extra read-model data, move that query into a service,
  repository, or dedicated `*_query_service.py` module.
- Controller-local workflow/presenter/serializer helpers inside `app/api/**`
  still count as controller logic when they coordinate config, storage,
  impersonation, translated response assembly, or other business flows. Move
  those seams into `*_workflow_service.py`, `*_query_service.py`, or a shared
  serializer module outside the controller file.
- AI dialogue backend paths must not accept, normalize, project, or preserve
  page-awareness fields such as `page_context`, `page_session_id`, `page_data`,
  `ui_*`, or `pageop_*`. When AI needs business data for analysis, expose it
  through explicit read-model/query APIs, report/export artifacts, or
  permissioned skill-pack tools instead of DOM/page perception compatibility.
- Treat `app/api/**` as transport-only. Any new `db.execute(...)`,
  `session.execute(...)`, raw `select(...)` assembly, or controller-local query
  helper is a design violation by default and must be moved into
  service/repository/query-service seams.
- Do not put repository responsibilities into services.
- Keep controllers, services, repositories, and runtime helpers high-cohesion:
  one dominant responsibility, one primary reason to change.
- Keep backend layers low-coupling: depend on controller/service/repository
  contracts instead of bypassing boundaries through lower-layer internals.
- If a backend module is oversized and mixes stable responsibilities, default to
  `thin facade + mixin/parts`:
  keep the public import/entry module stable, move real logic into focused
  sibling modules or a package, and preserve command names/routes/public imports.
- Once a facade is compatibility-only glue, keep new behavior out of it and
  continue splitting the heavier inner parts instead of reopening the facade
  for line-count-only churn.
- Do not return ad-hoc dict shapes; use `success()`, `created()`, `paginated()`,
  `deleted()`, or `error()`.
- Do not use `print()`, `logging.getLogger()`, or raw `loguru.logger`; use
  `app.core.logging`.
- Short-lived CLI and diagnostic entrypoints must default to console-only
  logging: set `NOVUSAI_CLI_DISABLE_FILE_LOGGING=1` before importing command
  modules that may initialize logging, and let `LogManager.init(..., enable_file=None)`
  honor that default so concurrent Windows processes do not spam `WinError 32`
  during shared log rotation.
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

## Governance Refactor Patterns (Executable)

Apply these defaults when refactoring non-AI control-plane or governance-heavy
backend modules:

- Oversized CLI: keep `app/cli.py` as thin facade, register command groups from
  `app/cli_commands/*`, and keep command names/options/import-visible helpers
  compatible.
- Base repository governance: keep `app/core/base_repository.py` as a facade
  over `app/core/repository_parts/*`; shared query/filter/tenant-scope logic
  belongs in the parts package, not in new repository helper buckets.
- Oversized controller families (`tasks`, `periodic_tasks`, plugin admin APIs):
  controller only parses request + delegates; query assembly lives in
  `*_query_service.py` or repository.
- Plugin platform backend: split by runtime concern
  (`lifecycle`, `registry`, `manifest/context`, read-model service, admin write workflow, cleanup service),
  avoid one module owning install/enable/migration/sync/audit simultaneously.
  已落地样例：`backend/app/plugins/lifecycle.py` 作为兼容 facade（443 行），
  `backend/app/plugins/lifecycle_orchestrator.py` 作为生命周期编排 parts（987 行）。
  `backend/app/api/admin/plugins.py` 的推荐写侧分层是：
  read routes -> `plugin_admin_contracts.py` / `plugin_read_model_service.py`；
  write routes -> `plugin_admin_workflow_service.py` / `plugin_cleanup_service.py` / `PluginService`。
  install-preview workflow 保持在 `plugin_install_preview_service.py`
  （token 编解码、marketplace/upload preview/confirm、package identity 校验）；
  `plugin_install_preview.py` 仅做路由/兼容导出，不回收进 `plugins.py`。
  `context.py` 可以保留 `PluginContext` 兼容入口，但 `RequestContext`、
  `PluginDbProxy`、`_NamespacedStorageProxy` 等共享原语应下沉到 companion
  modules（例如 `context_primitives.py`），调用方继续从
  `app.plugins.context` 获取稳定导出。
  `manifest.py` 可以保留 `PluginManifest` 等公共 schema 导出，但路径/handler/
  scope 校验常量与 helper 应下沉到 `manifest_helpers.py`，而 feature /
  dependency / pricing / resources 这类稳定元数据 schema 应继续下沉到
  companion modules（例如 `manifest_metadata_schemas.py`），避免 schema 主文件继续
  承担工具常量桶职责或重新膨胀回 1000+ 行。
- Codegen backend chain: separate generation core, config/read-model management,
  and CLI/API transport adapters; avoid one module owning config parse,
  generation orchestration, migration hooks, and delivery format at once.
- Codegen thin-facade pattern is acceptable when `codegen_service.py` and
  `codegen/generator.py` mainly compose `codegen_service_parts/*`,
  `generator_support.py`, `generator_context_builder.py`, and
  `generator_output_assembler.py`.
- Plugin-bundled backend services follow the same rule: keep package-facing
  facades thin, move overview/query/execution/scheduling logic into plugin-local
  modules, and preserve plugin runtime contracts.

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
- Thin facade + parts CLI pattern:
  `backend/app/cli.py` + `backend/app/cli_commands/*`
- Thin facade + mixin/parts plugin lifecycle pattern:
  `backend/app/plugins/lifecycle.py` + `backend/app/plugins/lifecycle_orchestrator.py`
- Plugin context primitives + facade pattern:
  `backend/app/plugins/context.py` + `backend/app/plugins/context_primitives.py`
- Plugin manifest facade + companion schema pattern:
  `backend/app/plugins/manifest.py` +
  `backend/app/plugins/manifest_metadata_schemas.py` +
  `backend/app/plugins/manifest_helpers.py`

## Anti-Patterns To Avoid

- Copying a pattern from another codebase that bypasses the NovusAI base
  classes.
- Adding a "quick" raw SQL path in a service instead of extending a repository.
- Swallowing exceptions with `except Exception: pass` or `continue`.
- Expanding legacy `200 + success=false` response shapes into new APIs.
- Re-implementing trace propagation or log formatting manually.
- Writing or editing fixed model-facing prompt text inline in Python instead of
  using the shared prompt contract resources.
- Letting one backend governance module become a business toolbox that mixes
  transport parsing, orchestration policy, persistence queries, and runtime glue.
