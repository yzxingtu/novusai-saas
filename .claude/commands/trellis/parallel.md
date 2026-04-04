# Parallel Work Orchestrator

Use this command only when the task truly benefits from parallel execution.

## Canonical Sources

Read these first:

1. `.trellis/workflow.md`
2. `.trellis/spec/guides/trellis-paths.md`
3. only the relevant indexes for the task:
   - `.trellis/spec/backend/index.md`
   - `.trellis/spec/frontend/index.md`
   - `.trellis/spec/ai-runtime/index.md`

Do not inject full workflow trees or use parallel mode as the default path.

## Required Behavior

1. Run `python3 ./.trellis/scripts/get_context.py`.
2. Choose `fast`, `normal`, or `deep` first.
3. Use parallel/multi-agent execution only for `deep` work where the write sets
   can stay disjoint.
4. Create or reuse a task with the path-driven contract:
   - `execution_path`
   - `required_artifacts`
   - `context_files`
   - `verification_mode`
5. Pass only task brief, exact target files, and capped excerpts to subagents.

## Retired Patterns

Do not instruct agents to follow:

- mandatory phase-era task lifecycles
- automatic worktree creation for ordinary tasks
- full-doc injection or broad repo rediscovery
- marker-based stop loops
- PR creation as part of task lifecycle

## Monitoring

If parallel execution is explicitly chosen, report status with the Trellis task
directory and the smallest useful monitoring command. Keep operator guidance
short and do not invent extra phases beyond the active task contract.
