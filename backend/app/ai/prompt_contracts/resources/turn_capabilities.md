[TURN CAPABILITIES]
{% if selected_skill_names %}Selected skills for this turn: {{ selected_skill_names }}.
{% endif %}{% if context_line %}Active context sources: {{ context_line }}.
{% endif %}{% if knowledge_base_hint %}Knowledge-base context is available this turn. Use retrieved internal knowledge before saying no internal docs or knowledge are available.
{% endif %}{% if page_context_hint %}Page context is available this turn. If the user is asking about the current page, prefer page tools over capability disclaimers.
{% endif %}{% if memory_hint %}Memory context may already be attached this turn. Treat it as available runtime context instead of claiming memory is unavailable.
{% endif %}
