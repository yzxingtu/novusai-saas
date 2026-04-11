## Agent Loop - Form Operation Workflow:
Execute ALL applicable steps in sequence WITHOUT stopping at the first tool call:
1. Call create_record/edit_record to open the form
2. Immediately call get_form_state to inspect current values and schema
RULE: Once the thin `page_context` snapshot is available for this turn, reuse that cached view instead of requesting another full context unless the UI reports the page changed.
规则：当本轮已经获得 thin `page_context` 快照后，只要页面未发生变化就复用该缓存视图，无需重新拉取完整上下文。
RULE: When the form is not open yet, DO NOT call get_form_options, fill_form, validate_form, or submit_form before create_record/edit_record opens it.
规则：当表单尚未打开时，禁止先调用 get_form_options / fill_form / validate_form / submit_form，必须先通过 create_record 或 edit_record 打开表单。
