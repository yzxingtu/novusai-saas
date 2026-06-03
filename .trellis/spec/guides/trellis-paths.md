# Trellis Paths

This guide is the canonical rule set for choosing `fast`, `normal`, or `deep`.

## Decision Order

Classify the work in this order:

1. Is this a direct answer or trivial edit?
2. Does the work need tracked requirements or resumable coordination?
3. Does the work contain uncertainty, cross-layer coupling, or staged execution that justifies a deep path?

Pick the first path that fully covers the need.

## Fast

Use `fast` when all of these are true:

- the goal is already clear
- the working set is small
- there is no meaningful ambiguity about architecture
- a task directory would add more overhead than value

Default behavior:

- no task by default
- no PRD by default
- no subagents by default
- no repo-wide research
- no workflow/spec full-text injection

Escalate out of `fast` if:

- acceptance criteria need to be tracked
- the file set expands materially
- the change crosses layers or contracts
- the task blocks on open design decisions

## Normal

Use `normal` when the work is clear but no longer trivial.

Default behavior:

- create a task when coordination or resumability helps
- require `prd.md`
- allow `info.md` only when design choices need to be frozen
- use only minimal `implement.jsonl` / `check.jsonl`
- verification is real commands, not ritual phases

Do not escalate to `deep` unless the task genuinely needs staged design or isolation.

## Deep

Use `deep` when at least one of these is true:

- architecture or interface redesign
- orchestration/governance refactor across multiple moving parts
- cross-layer contract changes
- the work should be decomposed and tracked over multiple execution passes

Default behavior:

- task required
- `prd.md` required
- `info.md` required
- curated context files required
- subagents/worktrees allowed, never automatic

## Context Budget Rules

Across all paths:

- prefer specific file paths over directories
- prefer excerpts over full documents
- prefer canonical index files over duplicated summaries
- keep injected context smaller than the likely coding payload

Recommended defaults:

| Path | Injection Style | Target Size |
|---|---|---|
| `fast` | task summary + exact files only | under 2 KB |
| `normal` | task summary + capped excerpts | under 6 KB |
| `deep` | task summary + curated excerpts + info summary | under 8 KB |

## Retired Patterns

These patterns are no longer valid Trellis behavior:

- “if in doubt, brainstorm + full task workflow”
- always create task + PRD + context files
- always create `implement`, `check`, and `debug` context files together
- marker-based stop loops
- implicit archive commits
- session-start injection of full workflow and full spec indexes

## Canonical References

- Workflow shell: `.trellis/workflow.md`
- AI runtime governance: `.trellis/spec/ai-runtime/index.md`
- Backend index: `.trellis/spec/backend/index.md`
- Frontend index: `.trellis/spec/frontend/index.md`
