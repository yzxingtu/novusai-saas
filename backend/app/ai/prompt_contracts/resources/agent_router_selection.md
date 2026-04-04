{% if vision_preamble %}{{ vision_preamble }}
{% endif %}{% if attachment_preamble %}{{ attachment_preamble }}
{% endif %}Based on the user's message and context, select the most appropriate agent.

Available agents:
{{ agent_list_json }}

{% if page_context_json %}Page context:
{{ page_context_json }}

{% endif %}User message: {{ message }}

Respond with ONLY a JSON object: {"agent_id": <id>, "confidence": <0.0-1.0>}
