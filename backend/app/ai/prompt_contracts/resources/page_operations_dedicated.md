[PAGE OPERATIONS]
Current page: {{ page_key }}{% if entity_desc %}
Page entity: {{ entity_desc }}
{% endif %}
Preferred: use dedicated pageop_* tools directly when available.
{% if dedicated_hint %}{{ dedicated_hint }}{% endif %}{% if mutation_hint %}{{ mutation_hint }}{% endif %}{% if editor_flow_hint %}{{ editor_flow_hint }}{% endif %}{% if other_ops_hint %}{{ other_ops_hint }}{% endif %}{% if screenshot_hint %}{{ screenshot_hint }}{% endif %}
Do NOT show HTML, JSON, tool params or call examples to the user. Tools are for internal execution; return natural language results only.{% if data_distinction_note %}{{ data_distinction_note }}{% endif %}
