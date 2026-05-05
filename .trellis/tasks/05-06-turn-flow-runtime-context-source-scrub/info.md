# Implementation Notes

## Root Cause

Two projection layers treated diagnostic `context_sources` as answer evidence:

- `backend/app/ai/engine/turn_flow_projector.py`
- `backend/app/services/ai/conversation_turn_flow_projector.py`

That was incorrect after the capability-bundle refactor. `context_sources` now
describe runtime inventory and context contributors; they are not citations.

## Design

- Engine turn-flow evidence resolves from `rag_sources` and tool results, not
  `context_sources`.
- Service read-model projection no longer builds canonical evidence from
  `context_sources`.
- The obsolete `context_sources -> evidence` helper was deleted so the new
  system has no misleading retained conversion path.
- Normalization filters non-tool evidence without a real URL, snippet, score,
  source reference, or badge.
- Normalization rewrites retrieval stages that only referenced filtered evidence
  to skipped/zero-evidence stages.
- Frontend `TurnFlowState` filters non-user-facing fallback evidence defensively.
- Frontend `TurnTimeline` expanded retrieval rows derive from sanitized
  `TurnFlowState` evidence instead of reparsing raw `msg.turnFlow`.
- Frontend kernel status treats terminal error surfaces and error stages as
  errors even if a partial assistant string exists.

## Break-Loop Analysis

- Root cause category: cross-layer contract plus test coverage gap.
- Specific cause: runtime `context_sources` were intended as diagnostic
  contributors, but backend read models and frontend state treated them like
  answer evidence. That let `skill_resolver`, inactive memory, and model
  capability diagnostics render as user-facing source counts.
- Prevention now in place: known-bug regression for conversation `2340`, CLI
  parity coverage for nested polluted `turn_flow` payloads, frontend state/UI
  regressions, Playwright smoke, and the AI runtime observability contract that
  keeps `context_sources` diagnostic-only.
