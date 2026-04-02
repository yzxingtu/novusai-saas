# Error Handling

> Error handling must preserve three things in this repo: user-safe messages,
> localized text, and traceability through `trace_id`.

## Core Response Contract

Use the response helpers in `backend/app/core/response.py`:

- `success()`
- `created()`
- `paginated()`
- `deleted()`
- `error()`
- `build_public_error_text()` / `build_error_payload()` for structured error
  paths

Do not return hand-built dicts with random keys for new APIs.
Do not "bare return" custom success payloads from ordinary CRUD handlers.

## Error Types

- Raise project exceptions for business failures:
  - `BusinessException`
  - `NotFoundException`
  - other app exception types already used in the module
- Use `HTTPException` when an HTTP-layer concern is genuinely the right
  primitive.
- Localize public messages with `_()`.
- Keep internal details in debug payloads or logs, not in user-facing strings
  by default.

Examples:

- Service exceptions: `backend/app/services/system/tenant_domain_service.py`
- HTTP-layer 404 in controller: `backend/app/api/tenant/domains.py`
- Public-safe payload helpers: `backend/app/core/response.py`

## Error Handling Patterns

- Validate request shape with schemas and controller-level dependencies first.
- Enforce business rules in services.
- Keep repository methods focused on data access; do not make them the home for
  user-facing exception wording.
- If a controller catches an exception, it should do so to map or enrich a
  response, not to suppress a bug.

Examples:

- Controller using service + wrapped success path:
  `backend/app/api/tenant/domains.py`
- Service business rule failures:
  `backend/app/services/system/tenant_domain_service.py`

## API Error Responses

- The current trace id comes from `TraceIdMiddleware` and `trace_id_var`.
- Public-facing error text should preserve `trace_id` when appropriate so UI
  and operators can correlate failures.
- Frontend 5xx and request-error UX depend on `X-Trace-ID` being propagated by
  backend middleware and response helpers.
- New APIs should prefer normal HTTP failure semantics over historical
  `200 + success=false` soft-failure shapes.
- If a legacy soft-failure path must remain, preserve `trace_id` and do not
  create a second, inconsistent error contract.

Primary files:

- `backend/app/middleware/trace.py`
- `backend/app/core/response.py`
- `frontend/apps/web-antd/src/utils/error-helpers.ts`

## Logging And Re-Raising

- Log errors through `get_logger(__name__)` or `LoggerMixin`.
- Keep logs structured enough to diagnose with `trace_id`.
- Do not log and then silently continue unless the path is explicitly optional
  and documented.
- Do not use `except Exception: pass` or `except Exception: continue`.

Examples:

- Trace-aware log patcher: `backend/app/core/logging.py`
- Task logging and rollback: `backend/app/tasks/ai.py`

## Common Mistakes

- Returning plain `{"message": "failed"}` from new endpoints.
- Throwing bare `Exception` for ordinary business validation.
- Swallowing errors in a broad catch without logging.
- Hardcoding visible strings instead of using `_()`.
- Hiding or stripping `trace_id` from operational failure paths.
