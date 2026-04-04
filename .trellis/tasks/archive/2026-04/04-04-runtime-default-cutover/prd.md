# Runtime Default Cutover

## Goal

Make runtime-v2 the only active runtime and delete compatibility routing and fallback behavior.

## Requirements

- Remove `legacy`, `shadow`, and `pageaware_only` runtime branching from the active path.
- Remove runtime fallback from v2 back to legacy.
- Delete `tool_invocation_planner.py` compatibility bridge and migrate affected tests/callers.
- Clean runtime-related env and documentation references.

## Ownership

- Allowed files:
  - `backend/app/ai/runtime/*`
  - `backend/app/ai/engine/tool_invocation_planner.py`
  - direct callers/tests/docs needed for the cutover
- Do not edit `conversation.py`, `stream_handler.py`, or `execution_state_machine.py`.

## Acceptance

- Runtime-v2 is the only default runtime.
- No active runtime path falls back to legacy.
- Compatibility planner is removed from active use.
