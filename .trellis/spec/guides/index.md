# Thinking Guides

> These guides surface the cross-layer contracts that keep NovusAI’s FastAPI
> backend, Vue/Vben frontend, AI stack, plugin framework, attachment system,
> domain routing, permissions, and trace/monitoring infrastructure aligned.

## Why We Think First

Our stack mixes backend services, Celery tasks, Vue components, Pinia/state,
AI agents/skills, plugins, uploads, domain detection, RBAC menus, and trace-aware
logging. The guides here make sure Codex/Claude/agents ask about the right
boundaries before they touch the repo.

## Available Guides

| Guide | Purpose | When to Use |
|-------|---------|-------------|
| [Code Reuse Thinking Guide](./code-reuse-thinking-guide.md) | Catch repeated patterns across services and pages | Anytime you repeat logic, constants, or configs |
| [Cross-Layer Thinking Guide](./cross-layer-thinking-guide.md) | Align backend frontend AI upload domain permission trace flows | Before touching work that spans multiple layers |
| [Announcement Contract](./announcement-contract.md) | Freeze announcement modal, notification click, delivery, and feedback receipt behavior | Before changing announcements or notification-center announcement handling |
| [Plugin Runtime Playbook](./plugin-runtime-playbook.md) | Freeze plugin manifest/runtime/permission/release contracts | Before changing plugin runtime, menus, assets, or packaging |
| [Repo Stabilization Workstreams](./repo-stabilization-workstreams.md) | Freeze dirty-tree boundaries into owned workstreams with merge/test gates | When the repo has broad parallel changes and needs phased stabilization |
| [Upstream/Downstream Governance](./upstream-downstream-governance.md) | Anchor Yudi as the multi-tenant SaaS upstream and point to customer fork, overlay, bugfix, release, and backport runbooks | Before governance audits, customer sync planning, or ambiguous upstream/downstream work |

## Quick Triggers

- Feature hits backend & frontend (example: `/api/tenant/domains` → Vue domain settings) → run the cross-layer checklist that references `.cursor/rules/tenant-architecture.md` and `backend/app/core/logging.py`.
- New module/helper/page/service is being added or an existing one is becoming
  "too big to reason about" → re-read `code-reuse-thinking-guide.md` and split
  the change to preserve high cohesion and low coupling.
- Feature adds attachments, downloads, or storage changes → ensure adherence to `.cursor/rules/attachments-and-storage.md`, `frontend/apps/web-antd/src/api/admin/attachment.ts`, `backend/app/services/system/attachment_service.py`.
- Feature modifies trace/monitoring, AI logging, or Celery queues → re-read `.cursor/rules/trace-and-monitoring.md`, `backend/app/tasks/ai.py`, `backend/app/middleware/trace.py`, minimize unwrapped trace_id manipulations.
- Feature touches permissions or domain isolation → check `.cursor/rules/rbac-and-data-permission.md`, `.cursor/rules/menu-i18n.md`, `frontend/apps/web-antd/src/directives/access.ts`, `backend/app/api/tenant/domains.py`.
- Feature adds plugin runtime or menu pieces → revisit `plugin-runtime-playbook.md` and `frontend/apps/web-antd/src/stores/plugin-slots.ts`.
- Repo is broadly dirty or active tasks overlap on the same files → use `repo-stabilization-workstreams.md` before proceeding so every file is either owned or explicitly frozen.
- Work may belong either to Yudi or to a customer repository → use
  `upstream-downstream-governance.md`, then follow
  `docs/guides/upstream-bugfix-policy.md` and
  `docs/operations/release-backport-policy.md` for the detailed fork, overlay,
  bugfix, release, and sync rules.

## How to Work the Guides

1. Pick the relevant guide from this directory.
2. Read the referenced canonical Trellis guides plus the real files that exemplify the contract.
3. Document any new lessons here so future agents can reuse them.

## Search Rule

Always search the value/path you plan to change before editing. Prefer `rg`
when it works in your environment, otherwise use `git grep` or PowerShell
search so you do not miss mirrored registrations. Our codegen and migrations
expect `backend/app/models/__init__.py` and `backend/migrations/env.py` to stay
in sync, so missing a place causes silent autogenerate failures.

## Core Principle

Two extra minutes of structured thinking now = no surprise of “cross-layer
contract broke everything” later.

That includes a simple architectural default: keep modules high-cohesion and
low-coupling, so each layer can change for its own reasons without dragging
unrelated surfaces along with it.
