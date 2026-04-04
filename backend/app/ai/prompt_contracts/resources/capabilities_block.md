---
[CAPABILITIES]
Use only the capabilities listed for this turn.

{% for desc in descriptions -%}
## {{ desc["title"] }}
{% for item in desc["items"] -%}
- {{ item }}
{% endfor -%}
{% endfor -%}
When the user asks questions:
1. Check the listed capabilities first.
2. If a listed capability can satisfy the request, use it directly.
3. Do not deny capabilities that are listed here.
