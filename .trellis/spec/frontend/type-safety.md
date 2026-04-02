# Type Safety

> TypeScript types should describe real backend contracts and the frontend
> transforms applied on top of them.

## Overview

- Use TypeScript across route pages, composables, API wrappers, stores, and
  shared utilities.
- Keep API raw payload shapes and frontend-consumed shapes separate when the
  backend uses snake_case and the UI uses camelCase.
- Prefer typed generics in shared CRUD and page-AI infrastructure.

Examples:

- API transform layer:
  `frontend/apps/web-antd/src/api/admin/attachment.ts`
- Generic CRUD list:
  `frontend/apps/web-antd/src/composables/use-crud-list.ts`
- Generic CRUD form:
  `frontend/apps/web-antd/src/composables/use-crud-form.ts`

## Type Organization

- Shared domain types live under `src/types/`.
- API modules may define raw response types close to the wrapper when the raw
  contract is specific to that endpoint.
- Keep route-only helper types local to the page when they are not reused.

Example:

- `frontend/apps/web-antd/src/types/attachment.ts`
- `frontend/apps/web-antd/src/api/admin/attachment.ts`

## Validation And Normalization

- Normalize backend payloads in API wrappers instead of scattering transform
  logic through Vue pages.
- Use shared request error normalization helpers for request failures.
- Keep attachment/image field semantics explicit; many fields are attachment ids
  first, URL strings second.

Examples:

- `transformAttachmentInfo()` in
  `frontend/apps/web-antd/src/api/admin/attachment.ts`
- Error normalization in
  `frontend/apps/web-antd/src/utils/error-helpers.ts`

## Common Patterns

- Use typed generics like `useCrudPage<T>` and `useCrudList<T>`.
- Use field lists and typed config objects to drive CRUD forms rather than
  repetitive untyped payload assembly.
- Use helper functions such as `parseAttachmentId()`,
  `toAttachmentImageUrl()`, and related image utilities for attachment-backed
  media fields.

Examples:

- `frontend/apps/web-antd/src/composables/use-crud-list.ts`
- `frontend/apps/web-antd/src/composables/use-crud-form.ts`
- `frontend/apps/web-antd/src/utils/image.ts`

## Forbidden Patterns

- `any` in business logic unless there is a narrow, justified boundary.
- Blind `as` casting to skip real typing work.
- Calling `Number()` or `parseInt()` on avatar/icon/image fields without
  confirming the field contract.
- Mixing backend snake_case objects directly into UI state without a clear
  transform layer.
- Building ad-hoc blob/download or upload types outside the shared request and
  attachment helpers.
