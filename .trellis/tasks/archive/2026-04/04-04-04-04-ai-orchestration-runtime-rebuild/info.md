# Implementation Notes

## Architecture Boundary

The new runtime is intentionally split into small components:

- `intent_planner.py`: structured intent slicing
- `path_selector.py`: `fast/normal/deep` selection
- `tool_router.py`: minimal candidate tool selection
- `execution_state_machine.py`: shared turn lifecycle
- `budget_guard.py`: hard stop-loss budgets
- `recovery_manager.py`: unfinished-intent retry + partial merge
- `failure_classifier.py`: provider/tool/orchestration/server interruption
- `turn_diagnostics.py`: compact trace payload

`conversation.py` and `stream_handler.py` now orchestrate through those
components rather than hosting divergent legacy loops.

## Removed Or Retired Behavior

- Regex-first mixed-family planner as the primary runtime routing mechanism
- Whole-turn contract retry as the default recovery path
- Repeated capability/tool awareness injection on every unchanged round
- Marker-based Trellis check loop
- Deleted compatibility plugin playbook under `.cursor/`
- Old duplicate non-stream execute block that survived below the new runtime
  implementation

## Governance Freeze

Canonical governance lives under:

- `.trellis/workflow.md`
- `.trellis/spec/backend/index.md`
- `.trellis/spec/frontend/index.md`
- `.trellis/spec/ai-runtime/index.md`
- `.trellis/spec/guides/index.md`

Entry-point docs under `.claude`, `.agents`, and `.cursor` should stay thin and
point back to those sources instead of copying long rule bodies.

## Validation Matrix

- Runtime engine tests:
  - `backend/tests/ai/engine/test_intent_planner.py`
  - `backend/tests/ai/engine/test_structured_orchestration_runtime.py`
  - `backend/tests/ai/engine/test_page_flow_recovery.py`
  - `backend/tests/ai/engine/test_cli_conversation_diagnostics.py`
  - `backend/tests/api/test_ai_conversation_router_diagnostics.py`
  - `backend/tests/test_ai_conversation_cli.py`
- Service integration tests:
  - `backend/tests/services/test_conversation_engine_prepare_execution.py`
  - `backend/tests/services/test_conversation_service.py`
  - `backend/tests/services/test_stream_handler_real_stream.py`
  - `backend/tests/services/test_runtime_v2_replay.py`
  - `backend/tests/services/test_monitoring_service.py`

## Rollout Expectation

This is a replacement, not a compatibility bridge. Old routing and governance
behavior should be removed once the new tests and diagnostics pass.
