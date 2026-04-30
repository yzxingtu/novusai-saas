# Page Operation WebSocket Retired

This reference is retained only for historical compatibility.

Do not add or reconnect AI dialogue page-operation WebSocket flows:

- `page_session_join` / `page_session_leave`
- `ui_action_invoke`
- `ui_snapshot_request`
- `ui_read_region_request`
- `ui_read_table_request`
- `ui_list_interactables_request`
- frontend `use-ui-action-channel.ts` for AI dialogue

If AI needs business data or actions, use backend-owned APIs, report/export
endpoints, explicit commands, or permissioned skill-pack tools instead of a
page-session socket channel.
