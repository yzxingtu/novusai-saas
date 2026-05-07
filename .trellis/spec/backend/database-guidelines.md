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

## Alembic Environment Registration Contract

`backend/migrations/env.py` is the executable contract that tells Alembic which
models and plugin migration paths participate in autogenerate and graph checks.
Treat changes here as infrastructure changes, even when the diff looks like
lint cleanup.

### Scope / Trigger

- Trigger: adding, moving, or deleting ORM model files under `backend/app/models/**`.
- Trigger: editing `backend/app/models/__init__.py`,
  `backend/migrations/env.py`, plugin migration path discovery, or Alembic
  autogenerate filters.
- Trigger: running Ruff fixes that touch import lists in `migrations/env.py` or
  model export packages.

### Signatures

The host model registration path must keep these surfaces:

```python
from app import models as registered_models
from app.core.base_model import Base

_registered_model_exports = registered_models.__all__
target_metadata = Base.metadata
_known_model_tables = set(target_metadata.tables.keys())
```

Plugin model discovery must import only plugin model packages that have a
`backend/models/__init__.py` and are returned by
`get_migration_plugin_names(...)`.

### Contracts

- Importing `app.models` must register every exported host model on
  `Base.metadata`.
- `registered_models.__all__` must include every handwritten host model that
  Alembic should see. A model that is only imported by routes, services, or
  codegen is not registered enough.
- `target_metadata` must be `Base.metadata`; do not build a second metadata
  object for migrations.
- Optional plugin model import failures may not crash host migration graph
  loading, but they must emit a visible warning with the plugin module name and
  exception text. Do not use silent `except Exception: pass` or
  `contextlib.suppress(Exception)` in Alembic registration code.
- `_include_object()` may filter reflected database tables that are not in
  `_known_model_tables`, but it must not filter host model tables out of
  metadata.

### Validation And Error Matrix

| Change | Failure Mode | Required Validation |
|---|---|---|
| Add a host model | Alembic autogenerate misses the table | Export it from `app.models.__all__` and assert the table appears in `Base.metadata.tables` |
| Ruff removes unused-looking model imports | Runtime still works but migrations miss models | Replace long imports with an explicit aggregate registration contract, then run Alembic graph checks |
| Plugin model package import fails | Silent missing plugin tables in autogenerate | Warning includes `plugins.<name>.backend.models` and the exception |
| `alembic heads` fails on Windows import root | `ModuleNotFoundError: migrations` during revision load | Run with `$env:PYTHONPATH='.'; alembic heads` from `backend/` |

### Good / Base / Bad Cases

Good:

```python
from app import models as registered_models
from app.core.base_model import Base

# 中文: 导入 app.models 包即可触发所有导出模型注册到 Base.metadata。
# EN: Importing app.models triggers registration of every exported model on Base.metadata.
_registered_model_exports = registered_models.__all__
target_metadata = Base.metadata
```

Base:

```powershell
python -m py_compile migrations/env.py
$env:PYTHONPATH='.'; alembic heads
python scripts/lint_migrations.py
python -c "from app import models; from app.core.base_model import Base; assert Base.metadata.tables"
```

Bad:

```python
try:
    importlib.import_module(_mod_name)
except Exception:
    pass
```

### Wrong Vs Correct

Wrong:

```python
# Ruff marks these imports unused, so they are removed without replacing the
# registration side effect.
from app.models.tenant.tenant import Tenant
from app.models.ai.agent import Agent
```

Correct:

```python
from app import models as registered_models

_registered_model_exports = registered_models.__all__
```

Wrong:

```python
with suppress(Exception):
    importlib.import_module(_mod_name)
```

Correct:

```python
try:
    importlib.import_module(_mod_name)
except Exception as exc:
    warnings.warn(
        f"Skip optional Alembic plugin model import {_mod_name!r}: {exc}",
        RuntimeWarning,
        stacklevel=2,
    )
```

### Tests Required

When touching Alembic env, model exports, or plugin migration discovery, run and
report:

- `python -m py_compile migrations/env.py`
- `$env:PYTHONPATH='.'; alembic heads`
- `python scripts/lint_migrations.py`
- A structural metadata assertion for representative host tables, for example:

```powershell
python -c "from app import models; from app.core.base_model import Base; assert 'tenants' in Base.metadata.tables; assert Base.metadata.tables"
```

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
- Keep Alembic revision identifiers within 32 characters because the default
  `alembic_version.version_num` column is `VARCHAR(32)`; use short stable IDs
  such as `20260507_0031_notif_gov` instead of long descriptive identifiers.
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
- Request-scoped async session helpers must treat `BaseException` as the
  rollback path, not only `Exception`, so `asyncio.CancelledError` during
  Ctrl+C shutdown or client disconnect does not escape from commit cleanup as a
  noisy false-positive error.

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
