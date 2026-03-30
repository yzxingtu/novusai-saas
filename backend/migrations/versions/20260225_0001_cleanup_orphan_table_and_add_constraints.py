"""cleanup: drop orphan table, add constraints, fix column drift

Revision ID: 20260225_0001
Revises: kb_attachment_null_tid
Create Date: 2026-02-25

Cleanup items:
1. Drop orphaned crud_generation_records table (model deleted, zero code references)
2. Add unique constraint on periodic_tasks.task_path for proper ON CONFLICT idempotency
3. Add missing deleted_at/delete_level columns to knowledge_base_tenant_access (schema drift)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '20260225_0001'
down_revision = 'kb_attachment_null_tid'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop orphaned table if it still exists (model was deleted during toolkit refactor)
    op.execute(sa.text("DROP TABLE IF EXISTS crud_generation_records CASCADE"))

    # 2. 多条 seed 可能插入相同 task_path；先按 task_path 去重（保留最小 id）再加唯一约束
    op.execute(
        sa.text(
            """
            DELETE FROM periodic_tasks AS a
            USING periodic_tasks AS b
            WHERE a.task_path = b.task_path AND a.id > b.id
            """
        )
    )

    # 3. Add unique constraint on task_path for idempotent seed migrations
    op.create_unique_constraint(
        'uq_periodic_tasks_task_path',
        'periodic_tasks',
        ['task_path'],
    )

    # 4. 历史漂移修复：kb_visibility_001 已带 deleted_at/delete_level，空库回放时跳过
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("knowledge_base_tenant_access"):
        cols = {c["name"] for c in insp.get_columns("knowledge_base_tenant_access")}
        if "deleted_at" not in cols:
            op.add_column(
                "knowledge_base_tenant_access",
                sa.Column("deleted_at", sa.DateTime(), nullable=True),
            )
        if "delete_level" not in cols:
            op.add_column(
                "knowledge_base_tenant_access",
                sa.Column("delete_level", sa.String(20), nullable=True),
            )


def downgrade() -> None:
    op.drop_column('knowledge_base_tenant_access', 'delete_level')
    op.drop_column('knowledge_base_tenant_access', 'deleted_at')

    op.drop_constraint('uq_periodic_tasks_task_path', 'periodic_tasks', type_='unique')

    # Recreate crud_generation_records (minimal schema for rollback)
    op.create_table(
        'crud_generation_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('table_name', sa.String(200), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('generated_code', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('delete_level', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
