[RESEARCH STATE]
{{ intro }}
Research target: {{ target }}.
Recent user research instructions:
{{ instruction_lines }}
Recent search queries: {{ recent_queries }}.
Completed search queries: {{ search_query_count }}.
Fetched detail pages: {{ fetched_url_count }}.
{% if extra_guidance %}{{ extra_guidance }}
{% endif %}Use this state as factual context for deciding whether more research is still needed.
