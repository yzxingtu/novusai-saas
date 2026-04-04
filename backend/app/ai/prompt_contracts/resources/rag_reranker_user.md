Query: {{ query }}

Document excerpts:
{% for excerpt in excerpts %}
[{{ excerpt.index }}] {{ excerpt.content }}
{% endfor %}

Rate each excerpt's relevance to the query (1-10):
