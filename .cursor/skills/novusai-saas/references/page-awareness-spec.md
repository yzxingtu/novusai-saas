# Page Awareness Retired

This file is retained only as a compatibility pointer for older tooling.

AI dialogue page awareness is retired. Do not create or extend:

- thin `page_context` contracts
- `page_data`, `page_session_id`, `ui_epoch`, active surface, or DOM snapshot
  payloads
- shared UI Runtime `ui_*` tools for AI dialogue
- page-session socket joins
- page-operation registries or page AI rails
- `get_page_context`, `invoke_page_operation`, or `list_page_operations`

Replacement architecture:

- AI read paths should use backend read models, query endpoints, report
  endpoints, exports, or permissioned skill-pack tools.
- AI write paths should use explicit backend commands or skill-pack tools with
  permission checks, validation, audit logging, and confirmation policy.
- Frontend UI may render AI results, but rendered DOM must not be the AI
  runtime source of truth.

The canonical active guidance now lives in:

- `.trellis/spec/ai-runtime/tool-skill-governance.md`
- `.trellis/spec/ai-runtime/frontend-ai-shell.md`
- `.trellis/spec/frontend/hook-guidelines.md`
