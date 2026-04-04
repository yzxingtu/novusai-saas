# Start Session

Use this command to initialize a Trellis-managed session without forcing a heavy workflow.

## Read First

Read these files in this order:

1. `.trellis/workflow.md`
2. `.trellis/spec/guides/trellis-paths.md`
3. the relevant index files only if the task needs them:
   - `.trellis/spec/backend/index.md`
   - `.trellis/spec/frontend/index.md`
   - `.trellis/spec/ai-runtime/index.md`

Do not read the full spec tree by default.

## Session Start

1. Run `python3 ./.trellis/scripts/get_context.py`
2. Summarize current developer / git / active-task state
3. Classify the user request into `fast`, `normal`, or `deep`
4. Proceed with the lightest path that fits

## Path Rules

| Path | Default Behavior |
|---|---|
| `fast` | answer directly or edit directly; no task by default |
| `normal` | create a task if tracking helps; require `prd.md`; keep context minimal |
| `deep` | require task + `prd.md` + `info.md`; use curated context only |

If the work is clear and bounded, do not escalate to brainstorm or deep path.

## Task Rules

- `fast`: do not create a task unless the user explicitly wants tracking
- `normal`: create a task when the work spans files or needs acceptance criteria
- `deep`: create a task before implementation

PR creation is not part of the default task lifecycle.

## Retired Behavior

Do not do any of the following by default:

- “if in doubt, brainstorm”
- mandatory research before coding
- mandatory phase-era task lifecycles
- marker-based check loops

## Subagents

Use subagents only when they materially reduce risk or isolate deep work.

When a subagent is used:

- inject task brief, exact target files, and capped excerpts
- do not inject full workflow/spec documents
- do not use directory-wide context loading
