# AI Orchestration Runtime Rebuild

## Goal

Rebuild the runtime orchestration kernel and Trellis governance layer so 661-666
style conversations no longer fail because of regex-family drift, whole-turn
retry loops, unbounded prompt growth, or heavy default workflow injection.

## Corrected Audit Statement

- `666` is not a single bad prompt incident.
- The primary cause is systemic orchestration failure: planner instability,
  whole-turn recovery, weak budget control, noisy provider/error attribution,
  and duplicated governance layers.
- Trellis was not the only direct runtime cause of `666`, but it mirrored the
  same governance smell by pushing heavy default paths and duplicated rules.

## Requirements

- Replace regex-first mixed-family planning with structured `IntentPlan[]`
  planning plus deterministic `fast/normal/deep` path selection.
- Unify streaming and non-streaming turns under one execution state machine.
- Enforce hard per-turn budgets for prompt size, tool rounds, retries, elapsed
  time, candidate tools, and tool-result bytes.
- Recover only unfinished intents; never retry an entire turn just because one
  intent failed.
- Separate orchestration failure from provider/tool/server interruption noise.
- Rebuild context injection to be budgeted, minimal, and one-shot for stable
  capability/tool summaries.
- Persist compact diagnostics so CLI inspection can explain a bad turn without
  scraping `app.log`.
- Keep Trellis, but convert it to path-based `fast/normal/deep` governance
  rather than mandatory heavy workflow phases.
- Make `.trellis/spec/**` the canonical governance source and thin out entry
  points in `.claude`, `.agents`, and `.cursor`.

## Acceptance Criteria

- `665` and `666` style identical inputs now produce the same intent plan and
  execution path.
- Multi-intent recovery retries only the unfinished intent and returns partial
  output when budgets or provider failures block full completion.
- Prompt/tool summaries are not re-injected every round when the active tool set
  is unchanged.
- `ai conversation show` exposes intent plan, path, budget, retries, and
  provider failure classification in compact form.
- Trellis start/session/subagent hooks inject only compact path/task context.
- Retired behaviors are removed: regex-first family planning, marker-loop check
  behavior, archive auto-commit, compatibility playbook duplication.
- Runtime regression tests and diagnostics tests pass.

## Out Of Scope

- Rewriting provider adapters or business tool executors from scratch
- Replacing RAG, quota accounting, or AIGateway with a new subsystem
- Reworking unrelated frontend/admin features outside the touched governance and
  diagnostics surfaces
