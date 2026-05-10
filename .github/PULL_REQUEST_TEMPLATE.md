## Summary

<!-- Explain the change and the product area it affects. -->

## Upstream / Downstream Decision

- [ ] This change belongs in `novusai-saas-yudi` because it affects shared SaaS product behavior.
- [ ] This change is customer-only and is intentionally limited to customer overlay/plugin/config/docs paths.
- [ ] Ownership was ambiguous, so the upstream/downstream decision is recorded in the linked Trellis task or issue.

Shared SaaS bugs and features must be fixed in Yudi first. Do not keep
long-lived downstream core patches in customer repositories. See
`docs/guides/upstream-bugfix-policy.md` and
`docs/guides/customer-fork-policy.md`.

## Risk Areas

Check every shared area touched by this PR:

- [ ] Auth, RBAC, tenant isolation, or account/session lifecycle
- [ ] Task queues, schedulers, retries, or background workers
- [ ] Notifications, delivery channels, or templates
- [ ] AI runtime, providers, agents, tools, memory, or dialogue flow
- [ ] Plugin framework, manifests, asset serving, or permissions
- [ ] Migrations, schema baseline, or seed data
- [ ] Docker, deployment, monitoring, or production acceptance
- [ ] Shared frontend shell, route guards, API clients, or components
- [ ] None of the above

## Verification

List the real commands or manual checks used for this change:

```text

```

For upstream-owned bug fixes:

- [ ] RED evidence is recorded before the fix.
- [ ] GREEN evidence is recorded after the fix.
- [ ] A customer sync path is documented when customers need the fix.

For customer repository syncs:

- [ ] Sync uses `merge upstream/<release>` or `cherry-pick -x <commit>`.
- [ ] `.yudi-base` is updated with `upstream`, `last_synced_at`, and `base_tag` or `base_commit`.
- [ ] `pwsh -File ops/verify-yudi-base.ps1 -Path <customer-repo>` passes.

For AI dialogue live paths:

- [ ] Tests are labeled `structural`, `behavioral`, or `smoke`.
- [ ] Behavioral/smoke tests avoid weak assertions and self-fulfilling mocks.
- [ ] Required real-dialogue smoke evidence is recorded or the blocker is stated.

## Release / Backport

- [ ] Target line is `main`.
- [ ] Target line is `release/x.y`.
- [ ] Target line is `hotfix/*`.
- [ ] No release/backport action is needed.

If this PR will be synchronized to customer repositories, record the target
release line, tag or commit, and rollback plan.
