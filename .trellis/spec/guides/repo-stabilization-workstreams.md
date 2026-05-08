# Repo Stabilization Workstreams

Use this guide when the repository already contains broad parallel changes and a
single “finish everything together” push would make ownership, rollback, and
verification unclear.

## Goals

- Freeze the dirty tree into explicit workstreams.
- Make every modified file belong to one active task or one frozen bucket.
- Validate each workstream independently before any combined assembly check.
- Prevent hidden scope creep while the repo is already unstable.

## Required Control Plane

When this guide is active:

1. Create one umbrella Trellis task with `execution_path=deep`.
2. Link every in-scope child task to that umbrella task.
3. Record a file ownership matrix with:
   - workstream
   - owning agent
   - owning task
   - owned file globs or exact files
   - risk level
   - merge order
   - test owner
4. Record a frozen backlog for any dirty files or tasks that are not yet clearly
   owned by a workstream.
5. Freeze any shared contracts or facade modules before parallel implementation
   starts.
6. Reserve `.trellis/tasks/{umbrella}/**` and `.trellis/spec/**` for the
   umbrella owner or an explicitly assigned docs-only worker when spec backfill
   is part of scope. Do not bury task/spec ownership inside one business
   workstream row.

Do not continue broad implementation until those six control-plane steps are
done.

## Workstream Rules

- One workstream owns one contract boundary.
- One worker owns one write set. If multiple workers are used, their write sets
  must be disjoint.
- Do not edit a file owned by another workstream unless the ownership matrix is
  updated first.
- If a workstream extracts a new facade, query service, or helper module from an
  owned giant file, add that new file to the ownership matrix in the same
  change; extracted files are not implicitly owned.
- Umbrella task docs/spec backfill is its own write set. Keep it under the
  umbrella owner or a docs-only worker; do not silently attach `.trellis/**`
  to a product workstream such as control-plane.
- If a file has already been reduced to a thin stable facade, mark the
  hotspot as closed in the umbrella notes and move the remaining work to the
  heavier extracted parts. Do not keep reopening the facade just because an
  older checklist still names that original file.
- Do not let “while I am here” edits leak into a nearby subsystem.
- Shared contracts may change only through the umbrella owner or a worker
  explicitly assigned to that shared seam.
- Do not merge the full repo in one shot.
- Do not treat warning-heavy test output as good enough. Warnings need either
  removal or an explicit waiver recorded in the owning task.

## Large-File Refactor Rule

When the repo-wide effort exists to reduce oversized files:

- do not split files just by line count
- split by stable responsibility boundaries
- prefer `facade file + internal package/modules` on backend
- prefer `page shell + composables + section components` on frontend
- for oversized CLI/ops scripts, keep the public command entry thin and move
  scaffold templates or static resource payloads into dedicated modules instead
  of leaving command parsing, templates, and runtime checks tangled together
- for plugin lifecycle/runtime governance, prefer `facade + mixin/parts`
  (example baseline: `lifecycle.py(443)` + `lifecycle_orchestrator.py(987)`)
- keep supported public import paths, routes, CLI command names, and runtime
  contracts stable unless the umbrella task explicitly declares a migration

### Recommended Seams For Plugin Platform And Codegen

When these domains are in-scope, default seam map is:

- plugin platform backend:
  facade/stable entry, lifecycle mixin/parts orchestration, registry/read model,
  cleanup/safety, transport adapters
- codegen backend:
  generator core, config/read-model manager, migration hook, transport adapters
- plugin/codegen frontend:
  page shell, workflow composables, section components

Do not replace this with one new "common manager" module.

## Merge Order

Default order:

1. Control plane and governance freeze
2. AI runtime core
3. Page-awareness retirement guard / provider / AI admin alignment
4. Plugin runtime and plugin-facing frontend
5. Permission / org / shared API
6. Final combined assembly verification

Reorder only if the umbrella task documents the reason.

## Validation Rules

- Each workstream must publish its own verification record before combined
  assembly starts.
- Combined assembly is allowed only after every in-scope workstream is either
  verified or explicitly frozen.
- Final assembly must be a composition check, not the point where new design is
  introduced.
- If the umbrella task required `.trellis/spec/**` backfill, that backfill is
  part of completion; it is not optional cleanup.
- Governance acceptance cannot pass when controller direct-query paths or
  frontend "business manager" pages remain in the claimed completed scope.

## Freeze Rules

- Unclassified dirty files are frozen.
- Tasks that still use legacy lifecycle metadata must be migrated to
  path-driven Trellis contracts before they continue.
- Archived or unrelated tasks do not inherit ownership automatically.
- `test-results/` and ad-hoc local artifacts never count as owned deliverables.

## Exit Criteria

The stabilization guide can be retired for a repo cycle only when:

- every active dirty file has a clear owner or frozen status
- every in-scope workstream has a verification record
- the final assembly check has run without introducing new design churn
