"""add_email_log_body_columns

Revision ID: c084bc659728
Revises: 31167c90d628
Create Date: 2026-02-22 16:23:41.827793+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c084bc659728'
down_revision: Union[str, None] = '31167c90d628'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.add_column('email_logs', sa.Column('html_body', sa.Text(), nullable=True, comment='HTML 正文内容'))
    op.add_column('email_logs', sa.Column('text_body', sa.Text(), nullable=True, comment='纯文本正文内容'))


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_column('email_logs', 'text_body')
    op.drop_column('email_logs', 'html_body')
