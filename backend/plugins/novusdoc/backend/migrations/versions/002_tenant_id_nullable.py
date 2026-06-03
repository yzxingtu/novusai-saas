"""use tenant_id=0 for admin/platform document space / 说明

Revision ID: novusdoc_002_tid_nullable
Revises: novusdoc_001_init
Create Date: 2026-03-15

Admin/platform documents use tenant_id=0, tenant documents use tenant_id=N.
FK constraint on tenants.id is dropped because 0 is a reserved sentinel,
not a real tenant record."""

import sqlalchemy as sa
from alembic import op

revision = "novusdoc_002_tid_nullable"
down_revision = "novusdoc_001_init"
branch_labels = None

TABLES = ("px_novusdoc_folders", "px_novusdoc_documents", "px_novusdoc_tags")

# Static SQL only (no f-string identifiers) / 表名白名单
_NULL_TENANT_TO_ZERO_SQL: dict[str, str] = {
    "px_novusdoc_folders": (
        "UPDATE px_novusdoc_folders SET tenant_id = 0 WHERE tenant_id IS NULL"
    ),
    "px_novusdoc_documents": (
        "UPDATE px_novusdoc_documents SET tenant_id = 0 WHERE tenant_id IS NULL"
    ),
    "px_novusdoc_tags": (
        "UPDATE px_novusdoc_tags SET tenant_id = 0 WHERE tenant_id IS NULL"
    ),
}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in TABLES:
        if table not in inspector.get_table_names():
            continue

        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            if "tenant_id" in fk.get("constrained_columns", []) and fk.get("name"):
                op.drop_constraint(fk["name"], table, type_="foreignkey")

        op.execute(sa.text(_NULL_TENANT_TO_ZERO_SQL[table]))
        op.alter_column(table, "tenant_id", nullable=False, server_default="0")


def downgrade():
    for table in TABLES:
        op.alter_column(table, "tenant_id", nullable=True, server_default=None)
