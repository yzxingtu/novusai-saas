# NovusDoc Writer plugin source sync

## Goal

Make `NovusDoc Writer` behave as a plugin-managed agent owned by the `novusdoc` plugin so the admin AI agent page shows its plugin source and its tenant distribution always follows the plugin's distribution rules.

## Requirements

- Add stable plugin-source metadata to agents.
- Backfill `NovusDoc Writer` to `source_plugin=novusdoc`.
- Keep plugin and agent tenant assignments synchronized in both directions.
- Show plugin source and synced distribution state in admin agent list/detail/form.
- Allow editing the selected-tenant set from the admin agent edit flow for plugin-managed system agents.

## Acceptance Criteria

- [ ] Admin agent list/detail return plugin source metadata for `NovusDoc Writer`.
- [ ] `NovusDoc Writer` scope and tenant assignments are synchronized with `novusdoc`.
- [ ] Editing selected tenants from `admin/ai/agents` updates both plugin and agent assignments.
- [ ] Tenant visibility follows existing RTA-based agent visibility rules without custom tenant filtering branches.
- [ ] Backend and frontend tests cover the new sync and rendering behavior.

## Technical Notes

- Backend + frontend + migration change.
- Plugin contract in `backend/plugins/novusdoc/plugin.yaml` stays unchanged.
- Current dirty worktree means edits must stay narrowly scoped to touched files only.
