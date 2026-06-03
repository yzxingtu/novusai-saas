"""add_routing_fields_to_ai_call_logs

Revision ID: 075fdfee8a70
Revises: f5b3f63a5364
Create Date: 2026-03-01 00:12:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '075fdfee8a70'
down_revision: Union[str, None] = 'f5b3f63a5364'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add routed_model_id and route_reason to ai_call_logs."""
    op.add_column(
        'ai_call_logs',
        sa.Column('routed_model_id', sa.Integer(), nullable=True,
                  comment='路由选出的模型 ID'),
    )
    op.add_column(
        'ai_call_logs',
        sa.Column('route_reason', sa.String(200), nullable=True,
                  comment='路由原因'),
    )
    op.create_foreign_key(
        'fk_ai_call_logs_routed_model_id_ai_models',
        'ai_call_logs', 'ai_models',
        ['routed_model_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index(
        op.f('ix_ai_call_logs_routed_model_id'),
        'ai_call_logs', ['routed_model_id'], unique=False,
    )


def downgrade() -> None:
    """Remove routing fields from ai_call_logs."""
    op.drop_index(
        op.f('ix_ai_call_logs_routed_model_id'), table_name='ai_call_logs',
    )
    op.drop_constraint(
        op.f('fk_ai_call_logs_routed_model_id_ai_models'),
        'ai_call_logs', type_='foreignkey',
    )
    op.drop_column('ai_call_logs', 'route_reason')
    op.drop_column('ai_call_logs', 'routed_model_id')
