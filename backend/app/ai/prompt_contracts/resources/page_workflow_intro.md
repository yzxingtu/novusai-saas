## Agent Loop - Form Operation Workflow:
Execute ALL applicable steps in sequence WITHOUT stopping at the first tool call:
1. Call create_record/edit_record to open the form
2. Immediately call get_form_state to inspect current values and schema
RULE: Once get_page_context has already returned the current page for this turn, do NOT call get_page_context again unless the page actually changes.
规则：当本轮已经成功获取当前页面上下文后，除非页面实际发生变化，否则不要再次调用 get_page_context。
RULE: When the form is not open yet, DO NOT call get_form_options, fill_form, validate_form, or submit_form before create_record/edit_record opens it.
规则：当表单尚未打开时，禁止先调用 get_form_options / fill_form / validate_form / submit_form，必须先通过 create_record 或 edit_record 打开表单。
