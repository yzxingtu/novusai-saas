---
name: ai-page-awareness
description: Retired. Do not use to build page awareness, page operations, thin page_context, shared UI Runtime ui_* tools, or page AI wiring.
---

# AI Page Awareness Skill Retired

Page awareness and page-operation wiring are retired for NovusAI AI dialogue.
Do not use this skill to add, repair, or re-enable any of these surfaces:

- `page_context`, `page_data`, `page_session_id`, `ui_epoch`
- DOM scanners, runtime snapshots, or thin page context builders
- `ui_*`, `pageop_*`, `get_page_context`, `invoke_page_operation`,
  `list_page_operations`
- `use-page-ai-operation-helpers`, `use-ui-action-channel`, page-operation
  registries, or page-session socket joins for AI dialogue

If AI needs to analyze page-visible or business data, expose that data through
one of the backend-owned seams instead:

- typed read-model/query API
- report/export endpoint
- permissioned installable skill-pack tool
- explicit backend command with authorization, validation, and audit logging

Historical references under `.cursor/skills/novusai-saas/references/` are
archive-only when they mention page awareness. The canonical active rule is:
do not rebuild page perception; design backend/skill data access instead.
