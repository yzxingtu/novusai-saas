Page context was already returned earlier in this turn. Reuse the previous get_page_context result unless the page actually changed.{% if page_key %} Current page: {{ page_key }}.{% endif %}
页面上下文在本轮已经返回过一次。除非页面实际发生变化，否则请复用上一次 get_page_context 结果，不要再次读取完整页面上下文。
