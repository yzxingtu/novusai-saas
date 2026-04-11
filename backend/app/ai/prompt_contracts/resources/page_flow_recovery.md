[PAGE FLOW RECOVERY]
You already returned a snapshot of the current page in this turn. Do NOT call ui_get_snapshot again unless the UI visibly changed.
If navigation is needed, discover targets with ui_list_interactables and open or click using ui_open_surface / ui_click.
After navigation succeeds, continue with the destination page's next real operation instead of stopping early.
