# Backend Business Code

Put project-specific backend domain code here.

Suggested split:

- `api/`: route handlers that stay transport-only.
- `models.py` or `models/`: project-owned tables.
- `repositories.py` or `repositories/`: database access.
- `services/`: business services and workflows.
- `tasks.py` or `tasks/`: scheduled and queued work.
- `tests/`: structural and behavioral tests.

Do not query or patch Yudi core internals directly from business routes. Shared
SaaS defects and missing platform hooks must be fixed in Yudi upstream first.
