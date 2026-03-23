# Workflow Orchestration Plugin

## Scope

This plugin delivers the workflow-orchestration product module shell with:

- plugin manifest and lifecycle entry
- plugin-owned persistence model under `px_workflow_orchestration_*`
- initial Alembic migration
- admin-side design-time APIs for overview, templates, releases, and settings
- stable database truth for AI-2 runtime implementation

## Zero-Host Boundary

The plugin keeps a strict zero-host persistence boundary:

- no writes to `backend/app/**`
- no writes to host frontend source
- no workflow business data stored in host core business tables
- no foreign keys to host tenant, user, or business entities
- module settings persist in `px_workflow_orchestration_module_configs`

The plugin intentionally does not use the host generic plugin config channel for design-time settings, because this delivery must keep all workflow-orchestration business state inside plugin-owned tables.

## Admin APIs

The current manifest exposes only admin routes:

- `GET overview`
- `GET metrics`
- `GET templates`
- `POST templates`
- `GET templates/{template_id}`
- `PUT templates/{template_id}`
- `GET templates/{template_id}/versions`
- `POST templates/{template_id}/publish`
- `GET releases`
- `POST releases/{release_id}/rollback`
- `GET settings`
- `PUT settings`

## Stable Model Truth For AI-2

AI-2 can treat the following tables and enums as frozen truth for runtime implementation:

- design-time: `templates`, `template_versions`, `template_nodes`, `template_edges`, `releases`, `triggers`, `environments`, `change_sets`, `module_configs`
- tenant/runtime support: `tenant_workflows`, `tenant_workflow_versions`, `runs`, `node_runs`, `checkpoints`, `events`, `artifacts`
- core design statuses: `draft`, `published`, `deprecated`, `archived`
- core runtime statuses: `pending`, `running`, `waiting_human`, `succeeded`, `failed`, `cancelled`

Version snapshots are immutable JSON documents carried by:

- `px_workflow_orchestration_template_versions.snapshot_json`
- `px_workflow_orchestration_tenant_workflow_versions.snapshot_json`

The snapshot contract includes:

- `snapshot_version`
- `workflow_schema_version`
- `contract_refs`
- `control_envelope_schema`
- `graph`
- `entrypoints`
- `defaults`
- `risk_policy_snapshot`
- `trigger_snapshot`
- `artifact_contracts`
- `output_contracts`
- `builder_surface`
- `compiled_at`
- `compiled_by`

## Runtime Compatibility

To keep the existing runtime code importable without touching forbidden files, the AI-1 delivery also provides:

- compatibility model modules:
  - `models.workflow_template`
  - `models.workflow_template_version`
  - `models.tenant_workflow`
  - `models.tenant_workflow_version`
  - `models.workflow_run`
  - `models.workflow_node_run`
  - `models.checkpoint`
  - `models.execution_checkpoint`
  - `models.event`
  - `models.execution_event`
  - `models.artifact`
  - `models.execution_artifact`
- SQLAlchemy-level alias fields consumed by runtime/query services, such as:
  - `workflow_template_id`
  - `tenant_workflow_id`
  - `workflow_run_id`
  - `workflow_node_run_id`
  - `input_payload`
  - `output_payload`
  - `snapshot_payload`
  - `detail`
  - `title`
  - `visibility`
  - `hash`

## Deferred Items

The following capabilities are intentionally deferred and recorded in the AI-1 handoff:

- runtime state machine
- tenant runtime APIs
- runtime task registrations
- frontend pages and route assets
- hosted webhook, event, and public trigger execution entrypoints
