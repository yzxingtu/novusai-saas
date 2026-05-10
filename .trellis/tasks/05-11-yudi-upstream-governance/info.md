# Design Notes

## Path Choice

This is a Trellis `deep` task because it defines a cross-repository development model that affects docs, release process, customer fork rules, developer workflow, and future bugfix routing.

## Canonical Direction

- This repository remains the canonical multi-tenant SaaS upstream.
- `novusai-admin` or other single-admin/custom projects are downstream or sibling products, not the active target state of this repository.
- Customer repositories may fork Yudi, but the expected shape is a thin fork:
  customer plugins, customer deployment overlays, customer configuration, customer data seeds, and customer business pages.
- Common platform defects must be fixed upstream first in Yudi.

## Work Packages

1. Docs and root navigation:
   update root/guide docs so developers can find the upstream/downstream rules.
2. Upstream bugfix policy:
   define triage, RED/GREEN regression, backport, and downstream sync flow.
3. Customer fork policy:
   define thin-fork allowed/disallowed changes and customer overlay layout.
4. Release/backport policy:
   define branch/tag/changelog/sync expectations.
5. Trellis/spec governance:
   make workflow/spec entries point to the new stable docs without duplicating detail.
6. Verification/check tooling:
   add lightweight base-version validation and run targeted scans.

## Verification Plan

- Parse the task JSON and JSONL records.
- Run markdown link/path sanity checks for the new docs when possible.
- Run targeted `rg` scans for contradictory guidance such as customer long-lived core patches.
- Run any added script with a passing and failing sample.
- Run `git diff --check`.

## Risk Notes

- These changes are governance and workflow changes. They do not, by themselves, make every existing customer fork thin or migrate existing downstream repositories.
- Future customer repositories must opt into the policy by adding upstream remotes and base metadata.
- If a future task changes code paths such as auth, tenant isolation, queues, notifications, AI runtime, or plugins, normal backend/frontend/AI verification still applies.
