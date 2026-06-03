<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

Use the `/trellis:start` command when starting a new session to:
- Initialize your developer identity
- Understand current project context
- Read relevant guidelines

Use `@/.trellis/` to learn:
- Development workflow (`workflow.md`)
- Project structure guidelines (`spec/`)
- Developer workspace (`workspace/`)

Keep this managed block so 'trellis update' can refresh the instructions.

<!-- TRELLIS:END -->

# Repo Navigation

- Start each session with `AGENTS.md`, `.trellis/workflow.md`, and
  `.trellis/spec/guides/trellis-paths.md`, then read only the relevant index
  files under `.trellis/spec/`.
- For governance or audit work, also check the relevant active task or recent
  audit note under `.trellis/tasks/` before promoting a new rule, so canonical
  spec files only absorb net-new stable facts.
- Governance and audit comparisons should use the current working-tree code and
  stable public route/import surfaces as evidence, not only previously committed
  prose.
- Before editing code, align with the owning canonical spec:
  - backend work -> `.trellis/spec/backend/index.md`
  - frontend work -> `.trellis/spec/frontend/index.md`
  - AI runtime, protocol/compat boundaries, package export/import seams, page
    tools, monitoring, routing, memory/context governance ->
    `.trellis/spec/ai-runtime/index.md`
  - cross-layer, plugin, or path-selection work -> `.trellis/spec/guides/*.md`
- Before claiming any AI dialogue change is "done", "fixed", "tests pass", or
  "regressions green", align with `.trellis/spec/ai-runtime/testing-discipline.md`:
  - Every test must be annotated `structural` / `behavioral` / `smoke`.
  - Weak assertions (`is not None`, `mock.called`, `len > 0` alone) and
    self-fulfilling mocks of LLM / tool executor / intent planner returns are
    forbidden in behavioral and smoke tests.
  - Milestone acceptance requires four simultaneous gates: structural +
    behavioral + smoke (real-dialogue) + known-bug (RED -> GREEN commit chain).
  - "All tests pass" or "no regressions" is NOT a sufficient statement of
    completion. Every PR touching AI dialogue live paths must answer the PR
    self-check in testing-discipline.md §7.
- Keep `AGENTS.md` as a navigation and governance entrypoint. Detailed rules
  belong in `.trellis/spec/**`, not here.
- When code and docs disagree, decide in this order:
  1. current stable code path in the working tree wins over stale prose for the
     local change
  2. if the pattern is repeated and intentional, update `.trellis/spec/**` in
     the same change
  3. if the evidence is partial, local, or still mid-refactor, do not
     generalize it; record it as governance debt or audit notes instead
- Governance or audit work should update the canonical spec/workflow files
  directly instead of leaving conclusions only in chat or task notes.
