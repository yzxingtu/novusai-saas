[PAGE OPERATIONS]
Current page: {{ page_key }}{% if entity_desc %}
Page entity: {{ entity_desc }}
{% endif %}
Available operations: {{ op_names }}
Call format: invoke_page_operation(page_key="{{ page_key }}", operation_name="<pick one>", params={...}){% if read_example %}{{ read_example }}{% endif %}{% if search_example %}{{ search_example }}{% endif %}{% if section_example %}{{ section_example }}{% endif %}{% if screenshot_guidance %}{{ screenshot_guidance }}{% endif %}{% if mutation_guidance %}{{ mutation_guidance }}{% endif %}{% if data_distinction_note %}{{ data_distinction_note }}{% endif %}
