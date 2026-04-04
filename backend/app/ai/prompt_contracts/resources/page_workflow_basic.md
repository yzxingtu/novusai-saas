## Agent Loop - Structured Form Workflow:
1. Call create_record or edit_record first.
2. Wait for the create/edit result before deciding the next action.
3. Call fill_form to fill ALL relevant fields
4. Wait for the fill_form result before deciding whether validation is needed
5. If validate_form exists, call validate_form and fix any errors
6. Wait for the validate_form result before deciding whether to submit
7. If submit_form exists and the user asked you to create/update the record, call submit_form
8. Only wait for user review when the page explicitly requires confirmation or submit_form is unavailable
RULE: Never batch create_record, get_form_state, get_form_options, fill_form, validate_form, or submit_form into the same assistant tool-call turn. Wait for each tool result before calling the next step.
规则：禁止把 create_record、get_form_state、get_form_options、fill_form、validate_form、submit_form 批量塞进同一轮 assistant tool calls，必须等上一步工具结果返回后再决定下一步。
IMPORTANT: Do NOT answer 'only read operations are available' when create_record/edit_record/fill_form/submit_form exist.
