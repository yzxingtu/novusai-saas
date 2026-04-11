Page context data was already returned earlier in this turn. Reuse the cached thin `page_context` snapshot unless the page actually changed.{% if page_key %} Current page: {{ page_key }}.{% endif %}
页面上下文在本轮已经返回过一次。除非页面实际发生变化，否则请复用先前缓存的 thin `page_context` 快照，不再重新获取完整页面上下文。
