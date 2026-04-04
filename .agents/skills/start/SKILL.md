---
name: start
description: "Start Session"
---

# Start Session

Thin entry point for Trellis-managed work.

## Canonical Sources

Read these files first:

1. `.trellis/workflow.md`
2. `.trellis/spec/guides/trellis-paths.md`
3. only the relevant indexes for the task:
   - `.trellis/spec/backend/index.md`
   - `.trellis/spec/frontend/index.md`
   - `.trellis/spec/ai-runtime/index.md`

Do not read all specs or all indexes by default.

## Required Behavior

1. Get current context with `python3 ./.trellis/scripts/get_context.py`
2. Classify the request into `fast`, `normal`, or `deep`
3. Use the lightest path that fits
4. Create a task only when the selected path requires or benefits from one

## Path Summary

| Path | Rule |
|---|---|
| `fast` | direct answer or direct edit; no task by default |
| `normal` | task recommended; require `prd.md`; minimal context |
| `deep` | task required; require `prd.md` + `info.md`; curated context only |

## Retired Patterns

Do not default to:

- brainstorm for ordinary implementation work
- mandatory research + jsonl setup for every task
- mandatory terminal lifecycle phases
- full workflow/spec injection
- marker-based stop loops

## Subagent Rule

If subagents are used, inject only:

- task brief
- exact target files
- capped excerpts
- minimal spec references
