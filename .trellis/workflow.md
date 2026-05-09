# Trellis Workflow

Trellis is the project task harness. It is not a mandatory heavy process.

The default rule is simple:

- Use the lightest path that can complete the work safely.
- Read only the specs needed for the current task.
- Create a task only when the work benefits from tracked requirements or multi-step coordination.
- Do not inject or read full workflow/spec trees by default.

## Source Of Truth

- Path rules: `.trellis/spec/guides/trellis-paths.md`
- Backend conventions: `.trellis/spec/backend/index.md`
- Frontend conventions: `.trellis/spec/frontend/index.md`
- AI runtime governance: `.trellis/spec/ai-runtime/index.md`

This repo's canonical docs describe the current multi-tenant SaaS system.
Single-instance split planning must not be kept as active canonical guidance in
this repo's `docs/**`, `.trellis/**`, or root entry documents.

All other command docs, hooks, and skills must stay thin and point back to these files.

## Governance Maintenance

- `AGENTS.md` is a navigation entrypoint, not a second copy of the spec body.
- Governance audits should start from `AGENTS.md`, this workflow file, the
  relevant spec indexes, and any recent related `.trellis/tasks/**` audit note,
  then compare those rules against the current code and public import/route
  surfaces.
- Promote only repeated, stable code facts into `.trellis/spec/**`.
- If a divergence is local, transitional, or obviously mid-refactor, capture it
  in an audit note or task record instead of weakening the global rule.
- When a repo pattern becomes canonical, update the owning spec file in the
  same change rather than leaving the rule only in task docs.

## Path Selector

Choose one path before doing substantial work.

| Path | Use When | Default Tasking | Default Context | Subagents |
|---|---|---|---|---|
| `fast` | question, trivial fix, one-file/small-scope change, direct audit answer | no task by default | only targeted files and the relevant index/spec | off by default |
| `normal` | clear implementation task across a few files | task recommended | `prd.md` plus minimal implement/check refs | optional |
| `deep` | ambiguous work, architecture change, multi-step refactor, cross-layer redesign | task required | `prd.md`, `info.md`, curated refs, explicit budgets | allowed, never default |

Do not upgrade to a heavier path just because the user asked a long question.

## Fast Path

Use `fast` when the work is direct and bounded.

- No task is required unless the user explicitly wants one.
- Do not create PRD/info/context files by default.
- Read only the exact files needed to answer or change the code.
- Do not start brainstorm, research, subagents, or worktrees unless the task actually stalls on uncertainty.

Typical examples:

- code explanation
- typo or copy fix
- one-file bug fix with clear cause
- focused audit of a specific function or command

## Normal Path

Use `normal` when the work benefits from lightweight task tracking.

- Create a task when the work spans multiple files, needs acceptance criteria, or should be resumable.
- `prd.md` is the only required planning artifact.
- `info.md` is optional; use it only if there are non-trivial design choices.
- Context files are optional and minimal. Default to `implement.jsonl` and `check.jsonl` only.
- Verification is real commands and real tests, not marker loops.

Typical examples:

- backend endpoint change with tests
- frontend page/composable change across a few files
- governance or CLI cleanup with a clear target

## Deep Path

Use `deep` only when the work is structurally complex.

- A task is required.
- `prd.md` and `info.md` are required.
- Context files must be curated, explicit, and small.
- Multi-agent, worktree, or parallel execution must be an explicit decision, not a fallback reflex.
- Research must output exact file paths and narrow examples, not broad repo summaries.

Typical examples:

- orchestration/runtime redesign
- cross-layer contract change
- broad refactor with multiple subsystems
- incident recovery plan requiring staged execution

## Task Lifecycle

Task lifecycle is path-driven, not phase-driven dogma.

- `fast`: usually no task
- `normal`: `plan -> active -> verified -> completed`
- `deep`: `plan -> designed -> active -> verified -> completed`

PR creation is not part of the task lifecycle. It is an optional release action.

## Context Rules

Context must be budgeted.

- Prefer explicit file paths over directories.
- Prefer excerpts over full file bodies.
- Prefer index files over full spec trees.
- Prefer `prd.md` / `info.md` summaries over repeated workflow text.
- Keep injected task context small enough that the subagent can still spend most of its context on the actual work.

Retired behavior:

- mandatory research before implementation
- mandatory PRD for simple work
- mandatory release-step lifecycle chaining
- full workflow/spec injection at session start
- directory-wide context loading
- marker-based check loops
- archive-time git mutations

## Verification

Verification must be command-driven.

- Run the smallest real validation set that can prove the change.
- If there is no meaningful automated validation, say so explicitly.
- Do not loop on text markers, “continue” prompts, or fake completion heuristics.

## Task Files

When a task exists, prefer this minimal contract:

- `task.json`: identity, path, status, ownership, lightweight lifecycle metadata
- `prd.md`: goal, requirements, acceptance criteria
- `info.md`: only for deep path or non-obvious design
- `implement.jsonl`: minimal implementation references
- `check.jsonl`: minimal verification references
- `debug.jsonl` / `research.jsonl`: deep path only, when justified

## Command Expectations

`task.py` should enforce the light-path defaults:

- default new task path is `normal`
- `--path fast|normal|deep` is explicit
- `init-context` creates only the files the selected path needs
- `archive` only archives; it never commits

## Start Session Rule

At session start:

- summarize current git/task state
- show the path selector
- show canonical spec entry points
- do not inject the full workflow or all spec indexes

## Subagent Rule

When subagents are used:

- pass task brief, exact target files, and capped excerpts
- do not pass entire docs or entire jsonl expansions
- do not mutate task progression through hidden marker logic
- do not rely on subagents to rediscover the whole repo
