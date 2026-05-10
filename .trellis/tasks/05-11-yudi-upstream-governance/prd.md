# PRD

## Goal

Make `novusai-saas-yudi` usable as the canonical SaaS upstream product line before customer project development starts.

The repository must clearly define where developers work, how customer forks stay thin, how common bugs flow back into Yudi, and how fixes are synchronized to customer delivery repositories.

## Non-Goals

- Do not convert this repository into the single-admin `novusai-admin` target.
- Do not add customer-specific code, customer names, or customer deployment secrets.
- Do not change runtime business behavior unless a small guard/test is needed to enforce the governance contract.
- Do not create compatibility patch guidance that encourages downstream long-lived fixes.

## Requirements

1. Define repository roles:
   - `novusai-saas-yudi` is the upstream SaaS product line.
   - Customer repositories are downstream thin forks or overlays.
   - Shared plugins or skill packages may live in reusable extension repositories when they are not core product code.
2. Define developer work location:
   - Common platform bugs and shared SaaS features are developed in Yudi first.
   - Customer-only workflows, branding, deployment overlays, and plugins stay in the customer repository.
   - Ambiguous changes require explicit upstream/downstream triage before implementation.
3. Define upstream-first bug flow:
   - Reproduce common bugs in Yudi with a focused regression test.
   - Fix and verify in Yudi.
   - Merge/backport/tag in Yudi.
   - Synchronize to customer forks with `merge upstream/<release>` or `cherry-pick -x`.
4. Define customer fork discipline:
   - Customer forks must stay thin.
   - Long-lived patches to auth, tenant isolation, task queues, notifications, AI runtime, plugin framework, migrations, Docker baseline, or shared UI are not allowed downstream.
   - Customer differences should prefer plugins, config, data seeds, branding, and deploy overlays.
5. Define release and backport policy:
   - `main` is the product integration line.
   - `release/x.y` is the stable customer delivery line.
   - `hotfix/*` is for urgent production repairs.
   - Customer repositories record their Yudi base tag/commit and sync history.
6. Define delivery evidence:
   - The task records implemented docs/specs/scripts and verification commands.
   - Release readiness is not claimed unless the required checks are run and recorded.

## Acceptance Criteria

- Canonical docs exist for repository strategy, upstream bugfix flow, customer fork policy, release/backport policy, and customer sync runbook.
- Trellis workflow/spec entry points reference the new governance docs without duplicating their full body.
- A lightweight script or checklist exists to verify a customer repository records its upstream Yudi base.
- Existing root docs direct developers to the upstream/downstream rules.
- Verification includes markdown/path sanity checks and targeted scans for contradictory guidance.
- Final answer lists what changed, what remains policy-only, and what future customer repositories must do.
