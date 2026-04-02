# Directory Structure

> How backend code is organized in NovusAI SaaS.

## Overview

The backend is a FastAPI application rooted at `backend/app/`. Files are
organized first by responsibility, then by scope. Scope matters: `admin`,
`tenant`, and `user` are separate surfaces and should not be mixed.

## Actual Directory Layout

```text
backend/app/
|-- api/            # FastAPI route layer split by admin/tenant/user/public/shared
|-- services/       # Business logic grouped by ai/system/tenant/common
|-- repositories/   # DB access grouped by ai/system/tenant
|-- models/         # SQLAlchemy models grouped by ai/auth/common/org/system/tenant
|-- schemas/        # Pydantic request/response schemas grouped by scope/domain
|-- core/           # Base classes, response wrappers, deps, security, logging
|-- middleware/     # Trace, tenant resolution, permission middleware
|-- tasks/          # Celery task modules registered with @register_task
|-- ai/             # Agent engine, routing, RAG, page tools, context engine
|-- rbac/           # Permission decorators, registry, sync, menus
|-- storage/        # Storage drivers and storage abstractions
|-- plugins/        # Host-side plugin runtime infrastructure
|-- locales/        # Backend i18n JSON files
|-- utils/          # Pure helpers only
|-- cli.py          # Single NovusAI CLI entrypoint
|-- main.py         # App bootstrap, middleware, router registration
```

## Placement Rules

### Controllers

- Put HTTP endpoints in `backend/app/api/{admin|tenant|user|public|shared}/`.
- Controllers should use `GlobalController` for platform scope and
  `TenantController` for tenant scope.
- Shared endpoints belong in `api/shared` only when they are intentionally
  reused across surfaces.
- User-facing APIs keep the fixed `/api/user/*` contract and should stay under
  `backend/app/api/user/`.
- User endpoints should continue to use the existing user-side auth conventions
  such as `ActiveTenantUser`, `@public`, and `@auth_only` rather than copying
  admin or tenant CRUD permission patterns blindly.

Examples:

- `backend/app/api/tenant/domains.py`
- `backend/app/api/admin/attachments.py`
- `backend/app/api/user/auth.py`

### Services

- Put business logic in `backend/app/services/`.
- Choose the directory by ownership:
  - `services/system/` for platform-wide services
  - `services/tenant/` for tenant-scoped business logic
  - `services/ai/` for AI, agents, memory, routing, RAG, and logging
  - `services/common/` for shared infrastructure helpers
- Write-path validation and protection should usually live in service hooks such
  as `_before_create`, `_before_update`, and `_before_delete`.
- Prefer `TenantService` or `GlobalService` over ad-hoc service classes.

Examples:

- `backend/app/services/system/tenant_domain_service.py`
- `backend/app/services/tenant/attachment_service.py`
- `backend/app/services/ai/agent_service.py`

### Repositories

- Repositories own query composition and persistence details.
- Put repositories in `backend/app/repositories/{ai|system|tenant}/`.
- Tenant-aware filtering must go through `TenantRepository` descendants.
- Data permission behavior belongs in repository/base-layer filtering, not
  service-level hand-built SQL.

Examples:

- `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
- `backend/app/repositories/system/tenant_domain_repository.py`
- `backend/app/repositories/ai/call_log_repository.py`
- `backend/app/core/base_repository.py`
- `backend/app/core/data_permission.py`

### Models And Schemas

- Models live in `backend/app/models/{domain}/`.
- Schemas live in `backend/app/schemas/{domain or scope}/`.
- Keep model and schema naming aligned so a feature is easy to trace end-to-end.

Examples:

- Model: `backend/app/models/tenant/tenant_domain.py`
- Schema: `backend/app/schemas/tenant/domain.py`
- Model export registry: `backend/app/models/__init__.py`

### Tasks

- Celery tasks live in `backend/app/tasks/`.
- Business task functions must use `@register_task`, not raw Celery decorators.
- Queue-specific infrastructure still belongs in `tasks/`, not in controllers
  or services.

Examples:

- `backend/app/tasks/ai.py`
- `backend/app/tasks/notification.py`
- `backend/app/tasks/scheduled.py`

### Plugins

- Host runtime infrastructure belongs in `backend/app/plugins/`.
- Plugin business code must stay under `backend/plugins/{plugin_name}/`.
- Do not place plugin-specific business logic in the host app except
  loader/runtime/permission bridge code.

## End-To-End Module Examples

### Tenant domain management

- Controller: `backend/app/api/tenant/domains.py`
- Service: `backend/app/services/system/tenant_domain_service.py`
- Tenant repository: `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
- Model: `backend/app/models/tenant/tenant_domain.py`

### Attachment pipeline

- Admin controller: `backend/app/api/admin/attachments.py`
- Tenant controller: `backend/app/api/tenant/attachments.py`
- Platform service: `backend/app/services/system/attachment_service.py`
- Tenant service: `backend/app/services/tenant/attachment_service.py`
- Model: `backend/app/models/tenant/attachment.py`

### AI feature chain

- Controller: `backend/app/api/admin/agents.py`
- Service: `backend/app/services/ai/agent_service.py`
- Task logging: `backend/app/tasks/ai.py`
- Audit logging: `backend/app/services/ai/action_log_service.py`

## Naming Conventions

- File names use snake_case.
- API files usually use plural resource names when they expose list/detail CRUD
  endpoints.
- Service files end with `_service.py`.
- Repository files end with `_repository.py`.
- Tenant-scoped repository names may include `_tenant_repository.py` when both
  global and tenant variants exist.
- Controller class names follow `{Scope}{Resource}Controller`.

## Required Follow-Up When Adding Files

- New models must be exported from `backend/app/models/__init__.py`.
- New handwritten models must also be imported in `backend/migrations/env.py`.
- New controllers must be imported and routed from the appropriate
  `backend/app/api/{scope}/__init__.py`.
- New controllers that participate in RBAC should also declare
  `@permission_resource(..., parent_resource=...)` and update the action
  translations in `backend/app/locales/*/messages.json`.
- New task modules must be reachable from Celery include/import paths.

## Anti-Patterns

- Putting data access in controllers.
- Adding scope-specific code to `shared/` just because it feels reusable.
- Creating one-off helper modules under `utils/` when the logic belongs in a
  service or repository.
- Writing plugin business logic into host `backend/app/` modules.
