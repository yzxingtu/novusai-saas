# Yudi Release and Backport Policy

This policy defines how `novusai-saas-yudi` publishes stable SaaS upstream
releases and how fixes flow into customer repositories. It is a governance
contract only; it does not replace the technical production gates in
`production-acceptance-runbook.md`.

## Branch Roles

- `main` is the product integration line. Shared SaaS features, common platform
  fixes, cross-tenant behavior, AI runtime changes, migrations, Docker baseline
  changes, plugin framework changes, and shared UI changes land here first.
- `release/x.y` is the stable customer delivery line for minor version `x.y`.
  It accepts only release stabilization, approved backports, documentation that
  affects delivery, and emergency fixes selected from `main`.
- `hotfix/*` is a short-lived urgent production repair branch. Create it from
  the affected `release/x.y` line or from the exact production tag when the fix
  must be isolated. Merge the verified hotfix back to the owning release line
  and forward-port it to `main`.

Do not develop customer-only branding, deployment overlays, data seeds, or
private plugins on Yudi release lines. Those belong in the customer repository.

## Tag Semantics

- Tags represent immutable Yudi release points. Use release tags for customer
  synchronization, support triage, and production evidence.
- Stable releases use `vX.Y.Z` tags created from `release/x.y`.
- Release candidates use `vX.Y.Z-rc.N` tags created from the same release line.
- Hotfix releases increment the patch number, for example `vX.Y.(Z+1)`, and the
  tag must point at the release line commit containing the hotfix.
- Never move or reuse a published tag. If a tagged release is wrong, publish a
  new patch tag and record the supersession in the changelog or release note.

Every customer delivery repository must record the Yudi base tag and exact Yudi
commit used for each sync. The base tag is the human release anchor; the commit
is the audit anchor when a customer repository needs to prove the exact source.

## Changelog and Upgrade Notes

Every release or backport must include operator-facing notes before it is
offered to customer repositories:

- changelog entry listing the merged fixes and any customer-visible behavior
  change
- upgrade notes for migrations, environment variables, Compose/deployment
  changes, plugin packaging changes, AI provider/runtime behavior, monitoring
  rules, and rollback constraints
- explicit compatibility notes when a customer repository must update overlays,
  seeds, plugins, or deployment configuration
- known-risk notes when a fix is policy-only, documentation-only, or depends on
  external acceptance evidence

Do not claim a release is ready just because the branch was merged or tagged.
Production acceptance remains gated by `production-acceptance-runbook.md` and
by any feature-specific checks required by the changed subsystem.

## Backport Eligibility

Backport to a customer stable line only when the change is common upstream value
or required for safe customer delivery:

- security fixes and data isolation repairs
- production incidents and urgent operational fixes
- regression fixes proven in Yudi with focused tests or acceptance evidence
- migration, deployment, monitoring, or rollback fixes needed by customer
  delivery
- low-risk documentation updates that unblock customer operations

Do not backport speculative refactors, unrelated cleanup, broad dependency
churn, or customer-only behavior. Customer repositories must stay thin; long
lived downstream patches to auth, tenant isolation, task queues, notifications,
AI runtime, plugin framework, migrations, Docker baseline, or shared UI are not
allowed as the normal fix path.

## Backport Flow

1. Triage whether the change is upstream common product work or customer-only
   overlay work.
2. Reproduce common defects in Yudi and add the smallest useful regression or
   acceptance evidence.
3. Fix and verify on `main`.
4. Merge the fix to `main`.
5. Select affected `release/x.y` lines and create a backport branch from each
   release line.
6. Apply the fix with merge or `cherry-pick -x` using the rules below.
7. Verify the release line with the smallest meaningful command set, plus any
   production gate affected by the change.
8. Update changelog and upgrade notes.
9. Merge the backport to `release/x.y`.
10. Tag a release candidate or patch release when the line is ready for
    customer synchronization.
11. Synchronize customer repositories and record their Yudi base metadata.

If a hotfix starts from a release line or production tag before the equivalent
fix exists on `main`, the hotfix must still be forward-ported to `main` after
production is stabilized.

## Merge vs Cherry-Pick

Use `merge` when preserving the branch relationship is more important than a
single isolated commit:

- synchronizing a customer repository from a Yudi release line with
  `merge upstream/release/x.y`
- bringing a complete stabilization branch into `release/x.y`
- applying a sequence of related commits where conflict resolution should be
  reviewed as one integration
- preserving release history for audit because the customer repository is a
  thin fork with minimal local divergence

Use `cherry-pick -x` when a specific commit must be traceable across lines:

- backporting one or a few fixes from `main` to `release/x.y`
- applying an urgent hotfix from a release line to a customer stable branch
- selecting only part of a larger feature after triage confirms it is safe
- customer repositories with local overlay commits where a full merge would
  pull unrelated upstream changes

The `-x` footer is required for backports and customer stable-line picks because
it records the original Yudi commit. Do not squash away that evidence.

## Customer Base Metadata

Each customer repository must keep `.yudi-base` at its repository root. JSON is
preferred, and `ops/verify-yudi-base.ps1` validates the required fields:

```json
{
  "schema": "yudi-base/v1",
  "upstream": "git@github.com:example/novusai-saas-yudi.git",
  "base_ref": "release/x.y",
  "base_tag": "vX.Y.Z",
  "base_commit": "<full-yudi-commit-sha>",
  "last_synced_at": "YYYY-MM-DD",
  "sync_method": "merge upstream/release/x.y",
  "sync_source": "upstream/release/x.y",
  "customer_sync_commit": "<customer-repo-commit-sha>"
}
```

`upstream`, `last_synced_at`, and either `base_tag` or `base_commit` are
required. A customer delivery handoff is incomplete when the repository cannot
answer:

- which Yudi tag it is based on
- which exact Yudi commit it includes
- which customer commit recorded the sync
- whether the sync used `merge` or `cherry-pick -x`
- which changelog and upgrade notes were applied

## Release Readiness Gate

Before a release line or customer sync is called ready, record:

- source branch and target branch
- Yudi base tag and commit
- merge or `cherry-pick -x` command used
- changelog and upgrade notes location
- verification commands and their result
- production acceptance evidence or explicit blocked gates

Policy-only documentation changes may use markdown/path sanity checks and
targeted contradiction scans. Runtime changes must use the subsystem-specific
backend, frontend, AI runtime, migration, deployment, and production acceptance
checks required by the touched code.
