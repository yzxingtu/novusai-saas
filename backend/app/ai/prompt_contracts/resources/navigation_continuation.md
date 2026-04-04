## Agent Loop - Cross-Page Navigation Workflow:
If the user's goal belongs to another page or menu, call navigate_menu first.
{{ list_available_menus_line }}
After navigate_menu succeeds, inspect the returned destination_ready and can_auto_continue fields before deciding whether to continue.
Only continue automatically when destination_ready=true and can_auto_continue=true.
If destination_ready=false, do NOT continue with follow-up write operations in the same turn. Return the partial navigation result and wait for the next page-read or retry step.
