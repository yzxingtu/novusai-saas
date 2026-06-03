Analyze this conversation turn and extract information worth remembering.

User message:
{{ message }}

Assistant response:
{{ response }}

Extract ONLY genuinely important items into these categories:
- preferences: User's stated preferences, likes, dislikes, preferred formats/tools/styles
- constraints: Explicit restrictions, rules, things to avoid, "don't do X"
- task_states: Current task progress, todos, next steps, ongoing work
- verified_facts: User's personal facts (name, role, company, tech stack, etc.)

Rules:
1. Only extract items the user explicitly stated or strongly implied
2. Summarize each item concisely (1 short sentence max)
3. If nothing worth remembering, return all empty arrays
4. Do NOT extract trivial greetings, acknowledgments, or filler
5. Do NOT repeat what the assistant said unless the user confirmed it as a preference

Respond ONLY with valid JSON (no markdown, no explanation):
{"preferences": [], "constraints": [], "task_states": [], "verified_facts": []}
