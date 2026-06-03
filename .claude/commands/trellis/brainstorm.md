# Brainstorm

Use this only when the work still has real ambiguity after a light Trellis path
selection. Brainstorm is no longer the default start flow.

## Canonical Sources

1. `.trellis/workflow.md`
2. `.trellis/spec/guides/trellis-paths.md`
3. Relevant indexes only if needed:
   - `.trellis/spec/backend/index.md`
   - `.trellis/spec/frontend/index.md`
   - `.trellis/spec/ai-runtime/index.md`

## When To Use

- architecture or interface choices are still open
- there are multiple valid approaches with meaningful trade-offs
- the task is likely `deep` and needs a frozen PRD before implementation

If the request is already clear and bounded, skip brainstorm and implement.

## Workflow

1. Inspect repo/docs first. Do not ask for information you can derive locally.
2. If the work needs tracked discovery and no task exists yet, create a
   path-appropriate task.
3. Create or update `prd.md` with:
   - goal
   - known facts
   - assumptions
   - open questions
   - requirements
   - acceptance criteria
4. Ask at most one blocking or preference question at a time.
5. When trade-offs are real, present 2-3 concrete options with consequences.
6. Stop once the MVP scope and recommended approach are clear.

## Guardrails

- Do not create a heavy path just because brainstorm exists.
- Do not run repo-wide research by default.
- Do not turn brainstorming into a mandatory phase gate.
- Do not keep the PRD vague after answers are available.

## Handoff

A brainstorm is done when `prd.md` is specific enough that implementation can
start without rediscovering the problem.
