# Implementation Notes

- Treat sync and stream as two transport shells over one logical state machine.
- Keep changes transport-local where needed, but keep outcome semantics identical.
- If a shared helper is needed outside the owned files, stop and hand back to the main agent.
