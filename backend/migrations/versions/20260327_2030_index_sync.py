"""Align runtime indexes with current models

Revision ID: 20260327_2030_index_sync
Revises: 20260327_1930_residual_schema
Create Date: 2026-03-27 20:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect


revision: str = "20260327_2030_index_sync"
down_revision: str | Sequence[str] | None = "20260327_1930_residual_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEXES_TO_CREATE = [
    ("agent_conversations", "ix_agent_conversations_owner_type", ["owner_type"]),
    ("agent_skill_grants", "ix_agent_skill_grants_recycle_stage", ["recycle_stage"]),
    ("ai_call_logs", "ix_ai_call_logs_access_channel", ["access_channel"]),
    ("ai_call_logs", "ix_ai_call_logs_actor_user_id", ["actor_user_id"]),
    ("ai_call_logs", "ix_ai_call_logs_agent_id", ["agent_id"]),
    ("ai_call_logs", "ix_ai_call_logs_agent_owner_tenant_id", ["agent_owner_tenant_id"]),
    ("ai_call_logs", "ix_ai_call_logs_agent_owner_type", ["agent_owner_type"]),
    ("ai_call_logs", "ix_ai_call_logs_agent_resource_scope", ["agent_resource_scope"]),
    ("ai_call_logs", "ix_ai_call_logs_conversation_id", ["conversation_id"]),
    ("ai_call_logs", "ix_ai_call_logs_tenant_publication_id", ["tenant_publication_id"]),
    ("capabilities", "ix_capabilities_recycle_stage", ["recycle_stage"]),
    (
        "px_storage_billing_provider_sources",
        "ix_px_storage_billing_provider_sources_is_deleted",
        ["is_deleted"],
    ),
    (
        "px_storage_billing_provider_sources",
        "ix_px_storage_billing_provider_sources_recycle_stage",
        ["recycle_stage"],
    ),
    ("px_storage_billing_runs", "ix_px_storage_billing_runs_is_deleted", ["is_deleted"]),
    (
        "px_storage_billing_runs",
        "ix_px_storage_billing_runs_recycle_stage",
        ["recycle_stage"],
    ),
    (
        "px_storage_billing_tenant_bindings",
        "ix_px_storage_billing_tenant_bindings_is_deleted",
        ["is_deleted"],
    ),
    (
        "px_storage_billing_tenant_bindings",
        "ix_px_storage_billing_tenant_bindings_recycle_stage",
        ["recycle_stage"],
    ),
    (
        "px_storage_billing_tenant_daily_charges",
        "ix_px_storage_billing_tenant_daily_charges_is_deleted",
        ["is_deleted"],
    ),
    (
        "px_storage_billing_tenant_daily_charges",
        "ix_px_storage_billing_tenant_daily_charges_recycle_stage",
        ["recycle_stage"],
    ),
    (
        "px_storage_billing_tenant_statements",
        "ix_px_storage_billing_tenant_statements_is_deleted",
        ["is_deleted"],
    ),
    (
        "px_storage_billing_tenant_statements",
        "ix_px_storage_billing_tenant_statements_recycle_stage",
        ["recycle_stage"],
    ),
    (
        "skill_capability_bindings",
        "ix_skill_capability_bindings_recycle_stage",
        ["recycle_stage"],
    ),
    ("skill_resources", "ix_skill_resources_recycle_stage", ["recycle_stage"]),
    ("skills", "ix_skills_source_type", ["source_type"]),
    ("skills", "ix_skills_status", ["status"]),
    (
        "tenant_agent_publications",
        "ix_tenant_agent_publications_enabled_for_users",
        ["enabled_for_users"],
    ),
    (
        "tenant_agent_publications",
        "ix_tenant_agent_publications_is_deleted",
        ["is_deleted"],
    ),
]

INDEXES_TO_DROP = [
    ("admin_org_scope_policies", "ix_admin_org_scope_policies_org_node_id"),
    ("capabilities", "ix_capabilities_key"),
    ("px_novusdoc_folders", "ix_px_novusdoc_folders_created_by"),
    ("px_novusdoc_tags", "ix_px_novusdoc_tags_created_by"),
    ("tenant_org_scope_policies", "ix_tenant_org_scope_policies_org_node_id"),
]

INDEXES_TO_RESTORE_ON_DOWNGRADE = [
    ("admin_org_scope_policies", "ix_admin_org_scope_policies_org_node_id", ["org_node_id"], True),
    ("capabilities", "ix_capabilities_key", ["key"], True),
    ("px_novusdoc_folders", "ix_px_novusdoc_folders_created_by", ["created_by"], False),
    ("px_novusdoc_tags", "ix_px_novusdoc_tags_created_by", ["created_by"], False),
    ("tenant_org_scope_policies", "ix_tenant_org_scope_policies_org_node_id", ["org_node_id"], True),
]


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _index_names(table_name: str) -> set[str]:
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if not _has_table(table_name):
        return
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if not _has_table(table_name):
        return
    if index_name not in _index_names(table_name):
        return
    op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    for table_name, index_name in INDEXES_TO_DROP:
        _drop_index_if_exists(table_name, index_name)

    for table_name, index_name, columns in INDEXES_TO_CREATE:
        _create_index_if_missing(table_name, index_name, columns)


def downgrade() -> None:
    for table_name, index_name, columns, unique in INDEXES_TO_RESTORE_ON_DOWNGRADE:
        _create_index_if_missing(
            table_name,
            index_name,
            columns,
            unique=unique,
        )

    for table_name, index_name, _columns in INDEXES_TO_CREATE:
        _drop_index_if_exists(table_name, index_name)
