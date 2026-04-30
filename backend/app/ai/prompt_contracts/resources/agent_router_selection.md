{% if vision_preamble %}{{ vision_preamble }}
{% endif %}{% if attachment_preamble %}{{ attachment_preamble }}
{% endif %}Based on the user's message, attachments, and conversation state, select the most appropriate agent.

Available agents:
{{ agent_list_json }}

User message: {{ message }}

Respond with ONLY a JSON object: {"agent_id": <id>, "confidence": <0.0-1.0>}
