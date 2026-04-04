# Implementation Notes

- Prefer deterministic fixtures over log scraping.
- Keep assertions focused on stable runtime semantics and surface fields.
- If a missing hook in production code blocks a test, stop and hand that exact blocker back to the main agent.
