[PAGE FLOW RECOVERY]
Use the current page state before repeating broad page reads.
If you already returned a snapshot of the current page in this turn, do NOT call ui_get_snapshot again unless the UI visibly changed.
If no active form is open yet, first discover the relevant trigger with ui_list_interactables and then open it with ui_open_surface / ui_click.
If navigation is needed, discover targets with ui_list_interactables and open or click using ui_open_surface / ui_click.
After opening the target surface, continue with the next real operation such as ui_get_form_state, ui_fill_form, or ui_submit_form instead of stopping early.
