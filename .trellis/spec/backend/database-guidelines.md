# Database Guidelines

> ORM, query, and migration conventions for the current SQLAlchemy/Alembic
> stack.

## ORM Baseline

- SQLAlchemy 2.x is the ORM.
- Async sessions are used in request code; Celery workers use sync sessions.
- Use the project base classes instead of raw SQLAlchemy base classes:
  - `BaseModel` / `TenantModel`
  - `BaseRepository` / `TenantRepository`
  - `BaseService` / `TenantService` / `GlobalService`

Representative files:

- `backend/app/models/tenant/tenant_domain.py`
- `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
- `backend/app/services/system/tenant_domain_service.py`

## Model Rules

- Tenant-owned tables should normally use `TenantModel`; platform tables use
  `BaseModel`.
- Declare `__filterable__` and `__sortable__` for list pages that support
  JSON:API-style filters and sorting.
- Declare `__selectable__` for remote select endpoints.
- Declare `__delete_deps__` when child records must be checked or cascaded in
  delete flows.
- If a resource needs AI visibility, follow the existing AI policy conventions
  instead of inventing new metadata.
- If a model participates in row-level access control, use the established
  data-permission hooks and metadata instead of hand-built service filters.

Examples:

- `backend/app/models/tenant/tenant_domain.py`
- `backend/app/models/tenant/attachment.py`
- `backend/app/models/ai/agent.py`

## Repository Rules

- Put query construction in repositories, not in controllers.
- Tenant-aware filtering must go through `TenantRepository` descendants.
- Row-level data permission belongs in repository/base-layer filtering driven by
  `__data_permission__`, ownership fields, and `data_permission_ctx`, not in
  custom service SQL.
- Creation defaults such as creator/org/dept ownership should continue to come
  from the existing base-repository data-permission machinery rather than being
  reimplemented in each service.
- If a model relies on parent-model data permission inheritance, keep that in
  the repository/base-layer contract instead of duplicating parent filters in
  business code.
- `PermissionMiddleware` populates `data_permission_ctx`; repository filtering
  should consume that context rather than recreating scope checks in services.
- Let repositories own field whitelists and list-query shape, rather than
  repeating filters in services.
- Use `select()`, repository helpers, and shared query/filter infrastructure
  before reaching for raw SQL.

Examples:

- `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`
- `backend/app/repositories/tenant/attachment_repository.py`
- `backend/app/repositories/ai/call_log_repository.py`
- `backend/app/core/base_repository.py`
- `backend/app/core/data_permission.py`
- `backend/app/middleware/permission.py`

## JSON:API Query Conventions

- List endpoints use `filter[...]`, `sort`, and `page[number]` /
  `page[size]`.
- New list APIs should be compatible with existing query parsing rather than
  introducing a custom filter protocol.
- Frontend-driven filtering only works for fields explicitly exposed through
  model/repository metadata.

Example:

- `backend/app/api/tenant/domains.py` documents filtering, sorting, and
  pagination in its list endpoint.

## Registration Rules For New Models

When adding a handwritten model:

1. Add the model file under the correct `backend/app/models/...` directory.
2. Export it from `backend/app/models/__init__.py`.
3. Import it in `backend/migrations/env.py` so Alembic autogenerate sees it.
4. Generate and review the migration.

Do not skip step 2 or 3. In this repo, model export and migration registration
are both part of the contract.

Examples:

- `backend/app/models/__init__.py`
- `backend/migrations/env.py`

## Migration Rules

- Alembic migrations must succeed on a fresh empty PostgreSQL database.
- Prefer inspect-first and idempotent logic over optimistic "try and ignore
  failure" code.
- A failed SQL statement poisons the current transaction; do not rely on
  `except: pass` to recover and continue in the same migration transaction.
- Use `conn.begin_nested()` for optional steps that may fail and must roll back
  independently.
- Inspect before `add_column`, inspect before updating a column that may already
  have been dropped, and inspect before dropping objects with branch-sensitive
  names.
- Do not use `text(f"...")` or interpolate identifiers into SQL strings.
- Use explicit `sa.String(length)` sizes for new string columns.
- Expand column length before updating to longer enum-like values.
- Use helper utilities such as
  `migrations.helpers.safe_rename_permission_resource()` when renaming unique
  RBAC resources.
- Deduplicate data before adding unique constraints.
- Use `IF EXISTS` or catalog checks when dropping indexes or tables whose names
  may differ across migration branches.
- Keep `down_revision` ordering semantically correct; table creation must
  happen before dependent constraints or data patches.
- Check head ordering on clean databases; fresh-install safety matters more than
  "works on my upgraded dev DB".

Primary migration rule source:

- `.cursor/rules/alembic-migration-authoring.md`

Concrete repo references:

- `backend/migrations/env.py`
- `backend/scripts/fresh_install_migrate_test.py`
- `backend/scripts/lint_migrations.py`
- `backend/plugins/<name>/backend/migrations/versions/`

## Naming Conventions

- Tables use snake_case and plural names, for example `tenant_domains`.
- Foreign keys use `{table_singular}_id` or the existing domain-specific field
  name.
- Index names follow explicit, descriptive names, for example
  `ix_tenant_domains_tenant_primary`.
- Column comments are bilingual strings inside the model when comments are
  needed.

Example:

- `backend/app/models/tenant/tenant_domain.py`

## Query And Transaction Rules

- Services orchestrate transactions and business validation.
- Repositories should not contain business-policy decisions.
- Celery tasks must use sync DB sessions and JSON-serializable return values.
- Avoid ad-hoc transaction tricks in migrations; use nested transactions or
  pre-checks when optional steps can fail.

Examples:

- Sync Celery write path: `backend/app/tasks/ai.py`
- Global service business logic: `backend/app/services/system/tenant_domain_service.py`
- Tenant repository query logic: `backend/app/repositories/tenant/tenant_domain_tenant_repository.py`

## Common Mistakes

- Raw SQL composed in services for ordinary CRUD.
- Adding new filter/sort behavior without exposing metadata in the
  model/repository layer.
- Writing migrations that only work on a partially upgraded developer database.
- Registering a model in codegen or routes but forgetting model export or
  Alembic import.
