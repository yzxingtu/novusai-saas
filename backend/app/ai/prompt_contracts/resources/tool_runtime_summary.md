---
[RUNTIME SUMMARY]
Execution path: {{ execution_path }}
Primary intents: {{ intent_summary }}
Allowed tools: {{ allowed_tools }}
Budgets: prompt<= {{ prompt_budget }}, tool_rounds<= {{ tool_round_budget }}, elapsed_ms<= {{ elapsed_budget_ms }}
Prefer the smallest tool sequence that can finish the remaining intents.
Stop after reporting completed work and the real reason for any unfinished part.
