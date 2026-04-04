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
   - owning task
   - owned file globs or exact files
   - risk level
   - merge order
   - test owner
4. Record a frozen backlog for any dirty files or tasks that are not yet clearly
   owned by a workstream.

Do not continue broad implementation until those four control-plane steps are
done.

## Workstream Rules

- One workstream owns one contract boundary.
- Do not edit a file owned by another workstream unless the ownership matrix is
  updated first.
- Do not let “while I am here” edits leak into a nearby subsystem.
- Do not merge the full repo in one shot.
- Do not treat warning-heavy test output as good enough. Warnings need either
  removal or an explicit waiver recorded in the owning task.

## Merge Order

Default order:

1. Control plane and governance freeze
2. AI runtime core
3. Page awareness / provider / AI admin alignment
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
