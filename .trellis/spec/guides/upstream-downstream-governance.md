# Upstream/Downstream Governance

This guide is the Trellis canonical entry for Yudi upstream/downstream
governance. It intentionally stays thin: the operational runbooks live in
`docs/guides/**` and `docs/operations/**`.

## Repository Roles

- `novusai-saas-yudi` remains the canonical multi-tenant SaaS upstream product
  line.
- Customer repositories are downstream thin forks or overlays.
- Downstream customer or vertical business code belongs under
  `business/<project-code>/`, not mixed into Yudi core `backend/app`,
  `frontend/apps`, migrations, AI runtime, task infrastructure, or shared
  platform packages.
- Customer deployment, config, seed, branding, and delivery overlays belong
  under `customer/<project-code>/`.
- Reusable non-core packages belong under `extensions/<package-code>/`.
- Shared plugins, skills, or reusable extensions may live outside this repo
  when they are not core product code.
- `novusai-admin` and other single-admin or customer-specific targets are not
  the active canonical direction of this repository.

## Work Location Rule

Develop common platform bugs and shared SaaS features in Yudi first. Customer
repositories are for business modules in `business/<project-code>/`, customer
overlays in `customer/<project-code>/`, and private or reusable extensions in
`extensions/<package-code>/` or a dedicated extension repository.

If ownership is ambiguous, record the upstream/downstream triage decision before
implementation. Do not start a core fix downstream and later decide whether it
belongs upstream.

## Canonical Runbooks

- Bug ownership, RED/GREEN upstream bugfix flow, downstream sync, and
  downstream patch discipline:
  `docs/guides/upstream-bugfix-policy.md`
- Release lines, backports, tags, customer base metadata, and customer sync
  evidence:
  `docs/operations/release-backport-policy.md`

These documents carry the customer fork and overlay rules. Do not duplicate
their full body in Trellis specs, root docs, command docs, hooks, or skills;
link to the owning runbook and summarize only the boundary needed for the
current decision.

## Governance Audit Checks

Governance audits must verify that downstream repositories remain thin.
Specifically, check whether any customer repository keeps long-lived core
patches in shared product areas such as auth/RBAC, tenant isolation, task
queues, notifications, AI runtime, plugin framework, migrations, Docker or CI
baseline, or shared UI.

Audits should also check whether customer business modules are isolated under
`business/<project-code>/`. Business code living directly in Yudi core
directories is treated as a downstream structure failure unless the change has
already been upstreamed as shared SaaS product work.

If a customer repository contains a temporary emergency core patch, audit for:

- a linked Yudi upstream bugfix PR or task
- an expiry condition such as `remove after vX.Y.Z sync`
- a follow-up sync record proving the patch was removed after merge or
  `cherry-pick -x` from Yudi

Long-lived customer-side core patches are governance failures. Common fixes
must flow back through Yudi, then synchronize downstream by merging the Yudi
release line or using `cherry-pick -x` with provenance.

## Evidence Rule

Do not claim release readiness, customer sync readiness, or governance
completion from policy text alone. Record the verification commands that were
run, or state explicitly when a change is documentation-only and validated by
markdown/path checks plus targeted contradiction scans.
