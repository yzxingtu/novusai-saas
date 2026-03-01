"""create storage migration tables

Revision ID: 001
Revises:
Create Date: 2026-02-28

branch_labels = ('plugin_storage_migration',)
"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None
branch_labels = ('plugin_storage_migration',)


def upgrade():
    op.create_table(
        'px_storage_migration_tasks',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('source_driver', sa.String(50), nullable=False, comment='Source storage driver'),
        sa.Column('target_driver', sa.String(50), nullable=False, comment='Target storage driver'),
        sa.Column('status', sa.String(20), nullable=False, default='pending',
                  comment='pending/running/paused/completed/failed/cancelled/rolling_back'),
        sa.Column('scope', sa.String(100), nullable=False, default='all',
                  comment='Migration scope: all or tenant:{id}'),
        sa.Column('total_files', sa.Integer(), nullable=False, default=0),
        sa.Column('migrated_files', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_files', sa.Integer(), nullable=False, default=0),
        sa.Column('skipped_files', sa.Integer(), nullable=False, default=0),
        sa.Column('total_bytes', sa.BigInteger(), nullable=False, default=0),
        sa.Column('migrated_bytes', sa.BigInteger(), nullable=False, default=0),
        sa.Column('concurrency', sa.Integer(), nullable=False, default=5,
                  comment='Max concurrent file transfers'),
        sa.Column('source_config_snapshot', sa.JSON(), nullable=True,
                  comment='Source storage config at creation time'),
        sa.Column('target_config_snapshot', sa.JSON(), nullable=True,
                  comment='Target storage config at creation time'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False, comment='Admin user ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(),
                  onupdate=sa.func.now()),
    )

    op.create_table(
        'px_storage_migration_logs',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('task_id', sa.BigInteger(),
                  sa.ForeignKey('px_storage_migration_tasks.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('attachment_id', sa.BigInteger(), nullable=False,
                  comment='Reference to attachments table'),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False, default=0),
        sa.Column('status', sa.String(20), nullable=False, default='pending',
                  comment='pending/success/failed/skipped'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('old_driver', sa.String(50), nullable=False),
        sa.Column('old_base_url', sa.String(500), nullable=False, default=''),
        sa.Column('new_driver', sa.String(50), nullable=True),
        sa.Column('new_base_url', sa.String(500), nullable=True),
        sa.Column('migrated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index(
        'ix_px_sm_logs_task_status',
        'px_storage_migration_logs',
        ['task_id', 'status'],
    )

    op.create_index(
        'ix_px_sm_tasks_status',
        'px_storage_migration_tasks',
        ['status'],
    )
    op.create_index(
        'ix_px_sm_tasks_created_at',
        'px_storage_migration_tasks',
        ['created_at'],
    )


def downgrade():
    op.drop_index('ix_px_sm_tasks_created_at', table_name='px_storage_migration_tasks')
    op.drop_index('ix_px_sm_tasks_status', table_name='px_storage_migration_tasks')
    op.drop_index('ix_px_sm_logs_task_status', table_name='px_storage_migration_logs')
    op.drop_table('px_storage_migration_logs')
    op.drop_table('px_storage_migration_tasks')
