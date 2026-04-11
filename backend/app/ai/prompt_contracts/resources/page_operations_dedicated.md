[PAGE OPERATIONS]
Current page: {{ page_key }}
Use the available ui_* tools directly; do NOT fall back to free-form descriptions.
- Readonly: {{ readonly_tools or "none" }}
- Actions (navigation / open): {{ action_tools or "none" }}
- Form read/write: {{ form_tools or "none" }}
- Safe write: {{ safe_write_tools or "none" }}
- Submit-required: {{ submit_tools or "none" }}
Return natural-language results only; do NOT show HTML/JSON/tool params to the user.
