"""create workflow orchestration plugin tables

Revision ID: wo_001_init
Revises:
Create Date: 2026-03-23

branch_labels = ('plugin_workflow_orchestration',)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "wo_001_init"
down_revision = None
branch_labels = ("plugin_workflow_orchestration",)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
    ]


def _jsonb_object() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def _jsonb_array() -> sa.TextClause:
    return sa.text("'[]'::jsonb")


_PLUGIN_TABLES = (
    "px_workflow_orchestration_templates",
    "px_workflow_orchestration_template_versions",
    "px_workflow_orchestration_template_nodes",
    "px_workflow_orchestration_template_edges",
    "px_workflow_orchestration_environments",
    "px_workflow_orchestration_change_sets",
    "px_workflow_orchestration_triggers",
    "px_workflow_orchestration_releases",
    "px_workflow_orchestration_module_configs",
    "px_workflow_orchestration_tenant_workflows",
    "px_workflow_orchestration_tenant_workflow_versions",
    "px_workflow_orchestration_runs",
    "px_workflow_orchestration_node_runs",
    "px_workflow_orchestration_checkpoints",
    "px_workflow_orchestration_events",
    "px_workflow_orchestration_artifacts",
)


def _create_base_indexes(table_name: str) -> None:
    op.create_index(f"ix_{table_name}_id", table_name, ["id"])
    op.create_index(f"ix_{table_name}_is_deleted", table_name, ["is_deleted"])
    op.create_index(f"ix_{table_name}_recycle_stage", table_name, ["recycle_stage"])


def _drop_base_indexes(table_name: str) -> None:
    op.drop_index(f"ix_{table_name}_recycle_stage", table_name=table_name)
    op.drop_index(f"ix_{table_name}_is_deleted", table_name=table_name)
    op.drop_index(f"ix_{table_name}_id", table_name=table_name)


def upgrade():
    op.create_table(
        "px_workflow_orchestration_templates",
        *_base_columns(),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column(
            "builder_surface",
            sa.String(length=64),
            server_default="platform_workflow_studio",
            nullable=False,
        ),
        sa.Column(
            "release_scope",
            sa.String(length=64),
            server_default="selected_tenants",
            nullable=False,
        ),
        sa.Column("tags_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_array(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("risk_policy_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("contract_summary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("default_trigger_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("latest_version_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_version_id", sa.Integer(), nullable=True),
        sa.Column("current_published_version_id", sa.Integer(), nullable=True),
        sa.Column("latest_release_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("code", name="uq_px_workflow_orchestration_templates_code"),
    )
    op.create_index(
        "ix_px_workflow_orchestration_templates_status",
        "px_workflow_orchestration_templates",
        ["status"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_templates_category",
        "px_workflow_orchestration_templates",
        ["category"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_templates_builder_surface",
        "px_workflow_orchestration_templates",
        ["builder_surface"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_templates_release_scope",
        "px_workflow_orchestration_templates",
        ["release_scope"],
    )

    op.create_table(
        "px_workflow_orchestration_template_versions",
        *_base_columns(),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("snapshot_version", sa.String(length=32), server_default="1.0.0", nullable=False),
        sa.Column("workflow_schema_version", sa.String(length=32), server_default="1.0.0", nullable=False),
        sa.Column("snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("release_notes", sa.Text(), nullable=True),
        sa.Column("compiled_at", sa.DateTime(), nullable=True),
        sa.Column("compiled_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("is_latest", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "template_id",
            "version_no",
            name="uq_px_workflow_orchestration_template_versions_template_version",
        ),
    )
    op.create_index(
        "ix_px_workflow_orchestration_template_versions_template_id",
        "px_workflow_orchestration_template_versions",
        ["template_id"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_template_versions_status",
        "px_workflow_orchestration_template_versions",
        ["status"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_template_versions_snapshot_hash",
        "px_workflow_orchestration_template_versions",
        ["snapshot_hash"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_template_versions_published_flags",
        "px_workflow_orchestration_template_versions",
        ["template_id", "is_latest", "is_published"],
    )

    op.create_table(
        "px_workflow_orchestration_template_nodes",
        *_base_columns(),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.String(length=120), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("timeout_minutes", sa.Integer(), nullable=True),
        sa.Column("retry_limit", sa.Integer(), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("position_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("input_contract_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("output_contract_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.UniqueConstraint(
            "template_id",
            "node_key",
            name="uq_px_workflow_orchestration_template_nodes_template_node",
        ),
    )
    op.create_index(
        "ix_px_workflow_orchestration_template_nodes_template_type",
        "px_workflow_orchestration_template_nodes",
        ["template_id", "node_type"],
    )

    op.create_table(
        "px_workflow_orchestration_template_edges",
        *_base_columns(),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("edge_key", sa.String(length=120), nullable=False),
        sa.Column("from_node_key", sa.String(length=120), nullable=False),
        sa.Column("from_port", sa.String(length=120), nullable=True),
        sa.Column("to_node_key", sa.String(length=120), nullable=False),
        sa.Column("to_port", sa.String(length=120), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("condition_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.UniqueConstraint(
            "template_id",
            "edge_key",
            name="uq_px_workflow_orchestration_template_edges_template_edge",
        ),
    )
    op.create_index(
        "ix_px_workflow_orchestration_template_edges_template_nodes",
        "px_workflow_orchestration_template_edges",
        ["template_id", "from_node_key", "to_node_key"],
    )

    op.create_table(
        "px_workflow_orchestration_environments",
        *_base_columns(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", sa.String(length=32), server_default="platform", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="provisioned", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("capability_boundary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("rollout_policy_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.UniqueConstraint("code", name="uq_px_workflow_orchestration_environments_code"),
    )
    op.create_index(
        "ix_px_workflow_orchestration_environments_scope_status",
        "px_workflow_orchestration_environments",
        ["scope", "status"],
    )

    op.create_table(
        "px_workflow_orchestration_change_sets",
        *_base_columns(),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("workflow_kind", sa.String(length=32), server_default="template", nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column(
            "environment_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=True),
        sa.Column("change_types_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_array(), nullable=False),
        sa.Column("impact_summary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("dependency_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("validation_result_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("rollback_plan_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.UniqueConstraint("code", name="uq_px_workflow_orchestration_change_sets_code"),
    )
    op.create_index(
        "ix_px_workflow_orchestration_change_sets_workflow_status",
        "px_workflow_orchestration_change_sets",
        ["workflow_kind", "workflow_id", "status"],
    )

    op.create_table(
        "px_workflow_orchestration_triggers",
        *_base_columns(),
        sa.Column("workflow_kind", sa.String(length=32), server_default="template", nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("workflow_version_id", sa.Integer(), nullable=True),
        sa.Column(
            "environment_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("owner_type", sa.String(length=32), server_default="platform", nullable=False),
        sa.Column("owner_tenant_id", sa.Integer(), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("auth_config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("mapping_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("risk_guard_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("next_trigger_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_px_workflow_orchestration_triggers_workflow_status",
        "px_workflow_orchestration_triggers",
        ["workflow_kind", "workflow_id", "status"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_triggers_type_owner",
        "px_workflow_orchestration_triggers",
        ["trigger_type", "owner_tenant_id"],
    )

    op.create_table(
        "px_workflow_orchestration_releases",
        *_base_columns(),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("workflow_kind", sa.String(length=32), server_default="template", nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("workflow_version_id", sa.Integer(), nullable=False),
        sa.Column(
            "change_set_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_change_sets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "environment_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("environment_code", sa.String(length=64), nullable=True),
        sa.Column("release_scope", sa.String(length=64), server_default="selected_tenants", nullable=False),
        sa.Column("channel", sa.String(length=32), server_default="stable", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("rollout_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rollback_of_release_id", sa.Integer(), nullable=True),
        sa.Column("rollback_target_release_id", sa.Integer(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.UniqueConstraint("code", name="uq_px_workflow_orchestration_releases_code"),
    )
    op.create_index(
        "ix_px_workflow_orchestration_releases_workflow_status",
        "px_workflow_orchestration_releases",
        ["workflow_kind", "workflow_id", "status"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_releases_scope_channel",
        "px_workflow_orchestration_releases",
        ["release_scope", "channel"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_releases_published_at",
        "px_workflow_orchestration_releases",
        ["published_at"],
    )

    op.create_table(
        "px_workflow_orchestration_module_configs",
        *_base_columns(),
        sa.Column("config_scope", sa.String(length=32), server_default="global", nullable=False),
        sa.Column("config_key", sa.String(length=120), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
    )
    op.create_index(
        "uq_px_workflow_orchestration_module_configs_global",
        "px_workflow_orchestration_module_configs",
        ["config_scope", "config_key"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )
    op.create_index(
        "uq_px_workflow_orchestration_module_configs_tenant",
        "px_workflow_orchestration_module_configs",
        ["config_scope", "config_key", "tenant_id"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )

    op.create_table(
        "px_workflow_orchestration_tenant_workflows",
        *_base_columns(),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("source_template_id", sa.Integer(), nullable=True),
        sa.Column("source_release_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("mode", sa.String(length=32), server_default="deterministic", nullable=False),
        sa.Column("editable_level", sa.String(length=32), server_default="tenant_simple", nullable=False),
        sa.Column("is_simple_builder", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("builder_surface", sa.String(length=64), server_default="tenant_template_editor", nullable=False),
        sa.Column("workflow_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("latest_version_no", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_version_id", sa.Integer(), nullable=True),
        sa.Column("active_version_id", sa.Integer(), nullable=True),
        sa.Column("current_release_id", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_px_workflow_orchestration_tenant_workflows_tenant_code",
        ),
    )
    op.create_index(
        "ix_px_workflow_orchestration_tenant_workflows_status",
        "px_workflow_orchestration_tenant_workflows",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_tenant_workflows_builder",
        "px_workflow_orchestration_tenant_workflows",
        ["builder_surface"],
    )

    op.create_table(
        "px_workflow_orchestration_tenant_workflow_versions",
        *_base_columns(),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_tenant_workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("source_template_version_id", sa.Integer(), nullable=True),
        sa.Column("snapshot_version", sa.String(length=32), server_default="1.0.0", nullable=False),
        sa.Column("workflow_schema_version", sa.String(length=32), server_default="1.0.0", nullable=False),
        sa.Column("snapshot_hash", sa.String(length=128), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("compiled_at", sa.DateTime(), nullable=True),
        sa.Column("compiled_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("is_latest", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "workflow_id",
            "version_no",
            name="uq_px_wo_twf_versions_wf_ver",
        ),
    )
    op.create_index(
        "ix_px_workflow_orchestration_tenant_workflow_versions_status",
        "px_workflow_orchestration_tenant_workflow_versions",
        ["workflow_id", "status"],
    )
    op.create_index(
        "ix_px_wo_twf_versions_snap_hash",
        "px_workflow_orchestration_tenant_workflow_versions",
        ["snapshot_hash"],
    )

    op.create_table(
        "px_workflow_orchestration_runs",
        *_base_columns(),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("workflow_template_id", sa.Integer(), nullable=True),
        sa.Column("workflow_version_id", sa.Integer(), nullable=True),
        sa.Column(
            "release_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_releases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "trigger_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_triggers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "environment_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_environments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("parent_run_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("entrypoint", sa.String(length=64), nullable=True),
        sa.Column("initiated_by", sa.Integer(), nullable=True),
        sa.Column("initiated_from", sa.String(length=64), nullable=True),
        sa.Column("started_by_type", sa.String(length=32), nullable=True),
        sa.Column("mode", sa.String(length=32), server_default="deterministic", nullable=False),
        sa.Column("current_node_key", sa.String(length=120), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_payload_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("output_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cost_summary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("control_envelope_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("budget_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("risk_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("code", name="uq_px_workflow_orchestration_runs_code"),
    )
    op.create_index(
        "ix_px_workflow_orchestration_runs_tenant_status",
        "px_workflow_orchestration_runs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_runs_workflow_version",
        "px_workflow_orchestration_runs",
        ["workflow_id", "workflow_version_id"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_runs_trace",
        "px_workflow_orchestration_runs",
        ["trace_id"],
    )

    op.create_table(
        "px_workflow_orchestration_node_runs",
        *_base_columns(),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("parent_node_run_id", sa.Integer(), nullable=True),
        sa.Column("node_key", sa.String(length=120), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("attempt_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("executor_type", sa.String(length=64), nullable=True),
        sa.Column("executor_ref", sa.String(length=255), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("input_envelope_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("output_envelope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cost_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("metrics_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "run_id",
            "node_key",
            "attempt_no",
            name="uq_px_workflow_orchestration_node_runs_run_node_attempt",
        ),
    )
    op.create_index(
        "ix_px_workflow_orchestration_node_runs_status",
        "px_workflow_orchestration_node_runs",
        ["tenant_id", "status"],
    )

    op.create_table(
        "px_workflow_orchestration_checkpoints",
        *_base_columns(),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_run_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_node_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("checkpoint_type", sa.String(length=64), server_default="state_snapshot", nullable=False),
        sa.Column("resume_token", sa.String(length=255), nullable=True),
        sa.Column("state_hash", sa.String(length=128), nullable=True),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("restored_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("resume_token", name="uq_px_workflow_orchestration_checkpoints_resume_token"),
    )
    op.create_index(
        "ix_px_workflow_orchestration_checkpoints_run_type",
        "px_workflow_orchestration_checkpoints",
        ["run_id", "checkpoint_type"],
    )

    op.create_table(
        "px_workflow_orchestration_events",
        *_base_columns(),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_run_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_node_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_level", sa.String(length=32), server_default="info", nullable=False),
        sa.Column("event_code", sa.String(length=120), nullable=True),
        sa.Column("status_from", sa.String(length=32), nullable=True),
        sa.Column("status_to", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_px_workflow_orchestration_events_run_type",
        "px_workflow_orchestration_events",
        ["run_id", "event_type"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_events_trace",
        "px_workflow_orchestration_events",
        ["trace_id"],
    )

    op.create_table(
        "px_workflow_orchestration_artifacts",
        *_base_columns(),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "node_run_id",
            sa.Integer(),
            sa.ForeignKey("px_workflow_orchestration_node_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("workflow_id", sa.Integer(), nullable=True),
        sa.Column("workflow_version_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), server_default="draft", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("schema_ref", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("storage_uri", sa.String(length=500), nullable=True),
        sa.Column("storage_path", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("visibility_scope", sa.String(length=64), server_default="tenant_visible", nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("feedback_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("download_filename", sa.String(length=255), nullable=True),
        sa.Column("retention_policy_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("ready_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("code", name="uq_px_workflow_orchestration_artifacts_code"),
    )
    op.create_index(
        "ix_px_workflow_orchestration_artifacts_run_status",
        "px_workflow_orchestration_artifacts",
        ["run_id", "status"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_artifacts_type_visibility",
        "px_workflow_orchestration_artifacts",
        ["artifact_type", "visibility_scope"],
    )
    op.create_index(
        "ix_px_workflow_orchestration_artifacts_hash",
        "px_workflow_orchestration_artifacts",
        ["content_hash"],
    )

    for table_name in _PLUGIN_TABLES:
        _create_base_indexes(table_name)

    environment_table = sa.table(
        "px_workflow_orchestration_environments",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("scope", sa.String()),
        sa.column("status", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
        sa.column("capability_boundary_json", postgresql.JSONB()),
        sa.column("rollout_policy_json", postgresql.JSONB()),
    )
    op.bulk_insert(
        environment_table,
        [
            {
                "code": "draft_env",
                "name": "Draft Environment",
                "description": "Design-time editing and draft validation.",
                "scope": "platform",
                "status": "provisioned",
                "sort_order": 10,
                "is_system": True,
                "capability_boundary_json": {
                    "automatic_triggers_allowed": False,
                    "external_write_allowed": False,
                    "target_surfaces": ["platform_workflow_studio"],
                },
                "rollout_policy_json": {
                    "release_allowed": False,
                    "observability_required": False,
                },
            },
            {
                "code": "test_env",
                "name": "Test Environment",
                "description": "Static validation, dry-run, and contract verification.",
                "scope": "platform",
                "status": "activated",
                "sort_order": 20,
                "is_system": True,
                "capability_boundary_json": {
                    "automatic_triggers_allowed": False,
                    "external_write_allowed": False,
                    "target_surfaces": ["platform_workflow_studio"],
                },
                "rollout_policy_json": {
                    "release_allowed": False,
                    "observability_required": True,
                },
            },
            {
                "code": "staging_env",
                "name": "Staging Environment",
                "description": "Pre-production validation and staged rollout rehearsal.",
                "scope": "platform",
                "status": "pilot",
                "sort_order": 30,
                "is_system": True,
                "capability_boundary_json": {
                    "automatic_triggers_allowed": True,
                    "external_write_allowed": False,
                    "target_surfaces": ["platform_workflow_studio"],
                },
                "rollout_policy_json": {
                    "release_allowed": True,
                    "observability_required": True,
                },
            },
            {
                "code": "prod_env",
                "name": "Production Environment",
                "description": "Formal production release and execution.",
                "scope": "platform",
                "status": "live",
                "sort_order": 40,
                "is_system": True,
                "capability_boundary_json": {
                    "automatic_triggers_allowed": True,
                    "external_write_allowed": True,
                    "target_surfaces": ["platform_workflow_studio"],
                },
                "rollout_policy_json": {
                    "release_allowed": True,
                    "observability_required": True,
                },
            },
            {
                "code": "tenant_sandbox",
                "name": "Tenant Sandbox",
                "description": "Tenant validation, sample runs, and training demonstrations.",
                "scope": "tenant",
                "status": "provisioned",
                "sort_order": 50,
                "is_system": True,
                "capability_boundary_json": {
                    "automatic_triggers_allowed": False,
                    "external_write_allowed": False,
                    "target_surfaces": ["tenant_template_editor", "tenant_simple_builder"],
                },
                "rollout_policy_json": {
                    "release_allowed": False,
                    "observability_required": False,
                },
            },
            {
                "code": "tenant_pilot",
                "name": "Tenant Pilot",
                "description": "Small-scale tenant pilot with real low-risk traffic.",
                "scope": "tenant",
                "status": "pilot",
                "sort_order": 60,
                "is_system": True,
                "capability_boundary_json": {
                    "automatic_triggers_allowed": True,
                    "external_write_allowed": False,
                    "target_surfaces": ["tenant_template_editor", "tenant_simple_builder"],
                },
                "rollout_policy_json": {
                    "release_allowed": True,
                    "observability_required": True,
                },
            },
            {
                "code": "tenant_prod",
                "name": "Tenant Production",
                "description": "Tenant formal production execution.",
                "scope": "tenant",
                "status": "live",
                "sort_order": 70,
                "is_system": True,
                "capability_boundary_json": {
                    "automatic_triggers_allowed": True,
                    "external_write_allowed": True,
                    "target_surfaces": ["tenant_template_editor", "tenant_simple_builder"],
                },
                "rollout_policy_json": {
                    "release_allowed": True,
                    "observability_required": True,
                },
            },
        ],
    )

    config_table = sa.table(
        "px_workflow_orchestration_module_configs",
        sa.column("config_scope", sa.String()),
        sa.column("config_key", sa.String()),
        sa.column("tenant_id", sa.Integer()),
        sa.column("version", sa.Integer()),
        sa.column("settings_json", postgresql.JSONB()),
        sa.column("notes", sa.Text()),
    )
    op.bulk_insert(
        config_table,
        [
            {
                "config_scope": "global",
                "config_key": "module_settings",
                "tenant_id": None,
                "version": 1,
                "settings_json": {
                    "max_parallel_runs": 20,
                    "run_timeout_minutes": 30,
                    "artifact_preview_budget": 16384,
                    "tenant_agentic_enabled_default": False,
                },
                "notes": "Initial global settings",
            },
            {
                "config_scope": "tenant_default",
                "config_key": "module_settings",
                "tenant_id": None,
                "version": 1,
                "settings_json": {
                    "simple_builder_enabled": True,
                    "template_editor_enabled": True,
                    "agentic_builder_enabled": False,
                    "max_agentic_steps": 8,
                },
                "notes": "Initial tenant defaults",
            },
        ],
    )


def downgrade():
    for table_name in reversed(_PLUGIN_TABLES):
        _drop_base_indexes(table_name)

    op.drop_index("ix_px_workflow_orchestration_artifacts_hash", table_name="px_workflow_orchestration_artifacts")
    op.drop_index("ix_px_workflow_orchestration_artifacts_type_visibility", table_name="px_workflow_orchestration_artifacts")
    op.drop_index("ix_px_workflow_orchestration_artifacts_run_status", table_name="px_workflow_orchestration_artifacts")
    op.drop_table("px_workflow_orchestration_artifacts")
    op.drop_index("ix_px_workflow_orchestration_events_trace", table_name="px_workflow_orchestration_events")
    op.drop_index("ix_px_workflow_orchestration_events_run_type", table_name="px_workflow_orchestration_events")
    op.drop_table("px_workflow_orchestration_events")
    op.drop_index("ix_px_workflow_orchestration_checkpoints_run_type", table_name="px_workflow_orchestration_checkpoints")
    op.drop_table("px_workflow_orchestration_checkpoints")
    op.drop_index("ix_px_workflow_orchestration_node_runs_status", table_name="px_workflow_orchestration_node_runs")
    op.drop_table("px_workflow_orchestration_node_runs")
    op.drop_index("ix_px_workflow_orchestration_runs_trace", table_name="px_workflow_orchestration_runs")
    op.drop_index("ix_px_workflow_orchestration_runs_workflow_version", table_name="px_workflow_orchestration_runs")
    op.drop_index("ix_px_workflow_orchestration_runs_tenant_status", table_name="px_workflow_orchestration_runs")
    op.drop_table("px_workflow_orchestration_runs")
    op.drop_index("ix_px_wo_twf_versions_snap_hash", table_name="px_workflow_orchestration_tenant_workflow_versions")
    op.drop_index("ix_px_workflow_orchestration_tenant_workflow_versions_status", table_name="px_workflow_orchestration_tenant_workflow_versions")
    op.drop_table("px_workflow_orchestration_tenant_workflow_versions")
    op.drop_index("ix_px_workflow_orchestration_tenant_workflows_builder", table_name="px_workflow_orchestration_tenant_workflows")
    op.drop_index("ix_px_workflow_orchestration_tenant_workflows_status", table_name="px_workflow_orchestration_tenant_workflows")
    op.drop_table("px_workflow_orchestration_tenant_workflows")
    op.drop_index("uq_px_workflow_orchestration_module_configs_tenant", table_name="px_workflow_orchestration_module_configs")
    op.drop_index("uq_px_workflow_orchestration_module_configs_global", table_name="px_workflow_orchestration_module_configs")
    op.drop_table("px_workflow_orchestration_module_configs")
    op.drop_index("ix_px_workflow_orchestration_releases_published_at", table_name="px_workflow_orchestration_releases")
    op.drop_index("ix_px_workflow_orchestration_releases_scope_channel", table_name="px_workflow_orchestration_releases")
    op.drop_index("ix_px_workflow_orchestration_releases_workflow_status", table_name="px_workflow_orchestration_releases")
    op.drop_table("px_workflow_orchestration_releases")
    op.drop_index("ix_px_workflow_orchestration_triggers_type_owner", table_name="px_workflow_orchestration_triggers")
    op.drop_index("ix_px_workflow_orchestration_triggers_workflow_status", table_name="px_workflow_orchestration_triggers")
    op.drop_table("px_workflow_orchestration_triggers")
    op.drop_index("ix_px_workflow_orchestration_change_sets_workflow_status", table_name="px_workflow_orchestration_change_sets")
    op.drop_table("px_workflow_orchestration_change_sets")
    op.drop_index("ix_px_workflow_orchestration_environments_scope_status", table_name="px_workflow_orchestration_environments")
    op.drop_table("px_workflow_orchestration_environments")
    op.drop_index("ix_px_workflow_orchestration_template_edges_template_nodes", table_name="px_workflow_orchestration_template_edges")
    op.drop_table("px_workflow_orchestration_template_edges")
    op.drop_index("ix_px_workflow_orchestration_template_nodes_template_type", table_name="px_workflow_orchestration_template_nodes")
    op.drop_table("px_workflow_orchestration_template_nodes")
    op.drop_index("ix_px_workflow_orchestration_template_versions_published_flags", table_name="px_workflow_orchestration_template_versions")
    op.drop_index("ix_px_workflow_orchestration_template_versions_snapshot_hash", table_name="px_workflow_orchestration_template_versions")
    op.drop_index("ix_px_workflow_orchestration_template_versions_status", table_name="px_workflow_orchestration_template_versions")
    op.drop_index("ix_px_workflow_orchestration_template_versions_template_id", table_name="px_workflow_orchestration_template_versions")
    op.drop_table("px_workflow_orchestration_template_versions")
    op.drop_index("ix_px_workflow_orchestration_templates_release_scope", table_name="px_workflow_orchestration_templates")
    op.drop_index("ix_px_workflow_orchestration_templates_builder_surface", table_name="px_workflow_orchestration_templates")
    op.drop_index("ix_px_workflow_orchestration_templates_category", table_name="px_workflow_orchestration_templates")
    op.drop_index("ix_px_workflow_orchestration_templates_status", table_name="px_workflow_orchestration_templates")
    op.drop_table("px_workflow_orchestration_templates")
