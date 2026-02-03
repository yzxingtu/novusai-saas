"""add login security fields

为 admins、tenant_admins、tenant_users 表添加登录安全相关字段：
- login_fail_count: 登录失败次数
- last_fail_at: 最后登录失败时间
- locked_until: 账户锁定到期时间

Revision ID: 20260123_0006
Revises: 20260123_0005
Create Date: 2026-01-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260123_0006'
down_revision: Union[str, None] = '20260123_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加登录安全字段"""

    # 为 admins 表添加字段
    op.add_column('admins', sa.Column(
        'login_fail_count',
        sa.Integer(),
        nullable=False,
        server_default='0',
        comment='登录失败次数'
    ))
    op.add_column('admins', sa.Column(
        'last_fail_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='最后登录失败时间'
    ))
    op.add_column('admins', sa.Column(
        'locked_until',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='账户锁定到期时间'
    ))

    # 为 tenant_admins 表添加字段
    op.add_column('tenant_admins', sa.Column(
        'login_fail_count',
        sa.Integer(),
        nullable=False,
        server_default='0',
        comment='登录失败次数'
    ))
    op.add_column('tenant_admins', sa.Column(
        'last_fail_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='最后登录失败时间'
    ))
    op.add_column('tenant_admins', sa.Column(
        'locked_until',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='账户锁定到期时间'
    ))

    # 为 tenant_users 表添加字段
    op.add_column('tenant_users', sa.Column(
        'login_fail_count',
        sa.Integer(),
        nullable=False,
        server_default='0',
        comment='登录失败次数'
    ))
    op.add_column('tenant_users', sa.Column(
        'last_fail_at',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='最后登录失败时间'
    ))
    op.add_column('tenant_users', sa.Column(
        'locked_until',
        sa.DateTime(timezone=True),
        nullable=True,
        comment='账户锁定到期时间'
    ))


def downgrade() -> None:
    """移除登录安全字段"""

    # 从 admins 表移除字段
    op.drop_column('admins', 'login_fail_count')
    op.drop_column('admins', 'last_fail_at')
    op.drop_column('admins', 'locked_until')

    # 从 tenant_admins 表移除字段
    op.drop_column('tenant_admins', 'login_fail_count')
    op.drop_column('tenant_admins', 'last_fail_at')
    op.drop_column('tenant_admins', 'locked_until')

    # 从 tenant_users 表移除字段
    op.drop_column('tenant_users', 'login_fail_count')
    op.drop_column('tenant_users', 'last_fail_at')
    op.drop_column('tenant_users', 'locked_until')
