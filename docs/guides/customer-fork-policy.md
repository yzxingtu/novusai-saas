# Customer Thin Fork Policy

## Scope

`novusai-saas-yudi` is the canonical upstream SaaS product line. Customer
repositories are downstream thin forks or overlay repositories used to deliver
customer-specific configuration, plugins, branding, data seeds, and deployment
shape without carrying long-lived product patches.

Use this policy before starting work in a customer repository and again before
opening a pull request that changes shared product behavior. For the operational
sync procedure, see
[Customer Sync Runbook](../operations/customer-sync-runbook.md).

## Repository Roles

| Repository type | Role | Expected work |
|---|---|---|
| Yudi upstream | Canonical multi-tenant SaaS product line | Shared platform fixes, shared SaaS features, common migrations, shared UI, plugin framework, runtime governance, release branches and tags |
| Customer repository | Downstream thin fork with sanctioned business and overlay roots | Customer or vertical business modules under `business/<project-code>/`; customer branding, deployment overlays, seed data, and delivery config under `customer/<project-code>/` |
| Reusable extension repository | Shared extension package outside core product | Plugins, skill packages, connectors, templates, or integration assets under `extensions/<package-code>/` when they are reusable across customers but are not core Yudi product code |

Common platform bugs and shared SaaS features must be developed in Yudi first.
Customer-only changes stay downstream. Ambiguous changes require explicit
upstream/downstream triage before implementation.

## Required Downstream Directory Roots

Customer forks must keep downstream work out of Yudi core directories unless the
change is intentionally upstreamed. Use these roots:

| Root | Use For | Do Not Use For |
|---|---|---|
| `business/<project-code>/` | Real customer or vertical business code: backend services, frontend pages, shared contracts, business adapters | Shared SaaS platform fixes, deployment overlays, one-off secrets |
| `customer/<project-code>/` | Deployment overlays, environment examples, seeds, branding, customer acceptance notes, fork decisions | Runtime business modules or long-lived core patches |
| `extensions/<package-code>/` | Reusable plugins, connectors, report packs, skill packages, integration assets | One-customer workflows or customer deployment config |

Yudi core directories such as `backend/app`, `frontend/apps`, shared platform
packages, migrations, task infrastructure, AI runtime, and plugin framework
belong to upstream product code. Do not put customer business modules there just
because the code is convenient to import.

## Required Customer Upstream Remote

Every customer repository that forks Yudi must keep an `upstream` Git remote
pointing at the Yudi SaaS repository:

```powershell
git remote add upstream <yudi-repo-url>
git fetch upstream --tags
git remote -v
```

The `origin` remote belongs to the customer delivery repository. The `upstream`
remote belongs to Yudi. Do not rename either remote in project documentation or
automation unless the customer repository has an explicit migration note.

## Required `.yudi-base` Metadata

Every customer repository must carry a `.yudi-base` file at its repository root.
This file records the Yudi base that the customer repository was last reviewed
or synchronized against. JSON is preferred because it is easy for automation to
validate:

```json
{
  "schema": "yudi-base/v1",
  "upstream": "git@github.com:example/novusai-saas-yudi.git",
  "base_ref": "release/x.y",
  "base_commit": "<full-yudi-commit-sha>",
  "base_tag": "vX.Y.Z",
  "last_synced_at": "2026-05-11T00:00:00+08:00",
  "sync_method": "merge",
  "sync_source": "upstream/release/x.y",
  "customer_repo": "<customer-repo-name>",
  "notes": "Initial customer delivery baseline."
}
```

Rules:

- `upstream`, `last_synced_at`, and either `base_tag` or `base_commit` are
  required. They are enforced by `ops/verify-yudi-base.ps1`.
- `base_commit` should be a full Yudi commit SHA that exists in
  `git rev-parse upstream/<base_ref>` history or is the exact cherry-picked
  source commit.
- `base_tag` should be present for release delivery. Omit it only for
  pre-release integration snapshots that record `base_commit`.
- `sync_method` must be `merge`, `cherry-pick`, or `initial-fork`.
- Update `.yudi-base` in the same customer pull request that synchronizes Yudi
  changes.
- Do not store customer secrets, URLs with credentials, tokens, or environment
  values in `.yudi-base`.

## Allowed Downstream Changes

Customer repositories may keep thin, customer-specific changes in these areas:

- Customer or vertical business modules under `business/<project-code>/`.
- Customer branding assets, theme variables, logos, display names, and localized
  customer copy under `customer/<project-code>/`.
- Customer deployment overlays such as Compose override files, Helm values,
  platform manifests, reverse-proxy configuration, domain/TLS wiring, and
  environment examples with no secrets under `customer/<project-code>/`.
- Customer configuration defaults, feature flags, tenant bootstrap data, data
  seeds, import fixtures, and customer-specific admin setup scripts under
  `customer/<project-code>/`.
- Customer-only plugins, skill packages, connectors, report templates, and
  workflow packages that use supported extension boundaries. If they are part
  of the project business domain, keep their implementation under
  `business/<project-code>/` and keep Yudi/plugin adapters thin.
- Customer-only pages or workflow screens under `business/<project-code>/` when
  they do not modify shared route, auth, permission, tenancy, plugin, AI
  runtime, or migration contracts.
- Documentation that explains the customer delivery environment, operator
  process, and customer-specific acceptance evidence.

## Disallowed Long-Lived Downstream Patches

Customer repositories must not carry long-lived patches to shared product
contracts or infrastructure. These changes must be fixed upstream in Yudi and
then synchronized downstream:

- Authentication, session, account lifecycle, or password/login policy core.
- Tenant isolation, organization boundaries, RBAC, permission checks, or data
  access guards.
- Task queues, schedulers, background workers, retry semantics, or job
  orchestration.
- Notifications, email/SMS/push delivery framework, message routing, or shared
  notification templates used by multiple tenants.
- AI runtime, agent turn flow, tool execution, provider gateways, memory,
  conversation state, prompt governance, or real-dialogue smoke gates.
- Plugin framework, plugin manifest schema, plugin loader, extension registry,
  plugin asset serving, skill package sync, or plugin permission model.
- Database migration framework, shared Alembic history, baseline schema,
  cross-tenant data model, or migration ordering.
- Docker baseline, base image assumptions, shared production Compose services,
  health/readiness contract, or common startup scripts.
- Shared UI shell, shared component library, global route guards, common admin
  pages, tenant console shell, or shared API clients.
- Compatibility patches that hide an upstream defect instead of fixing the
  owning Yudi contract.

If a downstream patch touches one of these areas, stop and open an upstream Yudi
issue or task. The customer repository may carry a short-lived emergency hotfix
only when production is blocked and the hotfix has a tracked upstream Yudi
follow-up with the same root cause.

## Overlay Priority

When customer behavior differs from Yudi, choose the narrowest supported overlay
before editing core code:

1. Customer or vertical business module under `business/<project-code>/`.
2. Configuration, feature flag, tenant data, or seed overlay under
   `customer/<project-code>/`.
3. Plugin, skill package, connector, or reusable extension under `extensions/`
   when it is not tied to one customer.
4. Deployment overlay such as Compose override, Helm values, ingress, secrets
   manager binding, or platform-specific runtime setting.
5. Yudi plugin adapter or business adapter that depends on stable Yudi APIs.
6. Upstream Yudi change, when the requirement is shared or needs a new core
   extension point.

Core forks are a last resort. A customer-only behavior that needs core changes
usually means Yudi needs an upstream extension point, policy hook, plugin
capability, or configuration boundary.

## Upstream-First Bug Flow

Use this flow for bugs that affect shared behavior or any disallowed downstream
area:

1. Reproduce the bug in Yudi with the smallest focused regression test or smoke
   scenario that proves the failure.
2. Fix the root cause in Yudi.
3. Verify the Yudi fix with the relevant structural, behavioral, smoke, or
   migration checks for the touched area.
4. Merge to `main` or the owning release branch. Use `hotfix/*` only for urgent
   production repairs.
5. Tag or record the Yudi base when the fix is ready for customer delivery.
6. Synchronize to customer repositories with `merge upstream/<release>` or
   `cherry-pick -x <commit>`.
7. Update `.yudi-base` and record customer regression evidence.

Do not mark the customer issue fixed because a downstream workaround exists.
The closure evidence must point back to the Yudi fix or a tracked, time-bounded
emergency hotfix that is being upstreamed.

## Release and Backport Policy

- `main` is the Yudi product integration line.
- `release/x.y` is the stable customer delivery line.
- `hotfix/*` is for urgent production repairs that must land quickly and then be
  merged or cherry-picked back into the owning integration/release lines.
- Customer repositories should synchronize from `release/x.y` for delivery and
  from `main` only for explicitly approved pre-release integration.
- A customer repository must record every sync in `.yudi-base` and in its
  customer release notes or pull request body.

## Pull Request Checklist

Before merging customer repository work, confirm:

- `git remote -v` shows `upstream` pointing at Yudi and `origin` pointing at the
  customer repository.
- `.yudi-base` exists and records the current Yudi base.
- The diff is limited to allowed downstream changes, or an upstream Yudi task is
  linked for every shared product change.
- Customer differences use plugin, config, data seed, branding, or deployment
  overlays before core patches.
- Yudi sync commits use `merge upstream/<release>` or `cherry-pick -x`.
- Migration and regression validation evidence is recorded for the customer
  environment.
