# AI Runtime Governance

This directory is the canonical governance source for runtime orchestration work.

Use these files when the task touches:

- intent planning
- tool routing
- execution loops
- context budget and prompt assembly
- recovery and stop-loss behavior
- diagnostics and trace surfaces
- tool/skill governance

## Files

| File | Purpose |
|---|---|
| `intent-routing.md` | structured intent planning, path selection, minimal tool routing |
| `execution-state-machine.md` | shared turn lifecycle for streaming and non-streaming execution |
| `context-budget.md` | prompt/context/tool-result budget rules |
| `recovery-stop-loss.md` | unfinished-intent recovery, partial exit, and stop-loss rules |
| `observability.md` | turn diagnostics, trace fields, and CLI/operator visibility |
| `tool-skill-governance.md` | trigger boundaries, mutual exclusion, and budget-aware routing |

## Canonical Rule

Project rules, hooks, and commands must reference this directory instead of copying long AI runtime guidance into multiple places.
