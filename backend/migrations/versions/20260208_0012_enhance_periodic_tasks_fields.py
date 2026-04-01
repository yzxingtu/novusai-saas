"""enhance periodic_tasks fields: scope, protection, retry, notification

Revision ID: 20260208_0012
Revises: 20260208_0011
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260208_0012"
down_revision = "20260208_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "scope",
            sa.String(length=40),
            nullable=False,
            server_default="platform",
            comment="作用范围（platform/tenant/all_tenants）",
        ),
    )
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "is_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="是否禁止删除",
        ),
    )
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "is_editable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="是否允许编辑",
        ),
    )
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "max_retries",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="最大重试次数",
        ),
    )
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "retry_delay",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("60"),
            comment="重试间隔（秒）",
        ),
    )
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "timeout",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3600"),
            comment="执行超时（秒）",
        ),
    )
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "notify_on_failure",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="失败时是否通知",
        ),
    )
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "notify_emails",
            sa.Text(),
            nullable=True,
            comment="通知邮箱列表（逗号分隔）",
        ),
    )
    op.create_index("ix_periodic_tasks_scope", "periodic_tasks", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_periodic_tasks_scope", table_name="periodic_tasks")
    op.drop_column("periodic_tasks", "notify_emails")
    op.drop_column("periodic_tasks", "notify_on_failure")
    op.drop_column("periodic_tasks", "timeout")
    op.drop_column("periodic_tasks", "retry_delay")
    op.drop_column("periodic_tasks", "max_retries")
    op.drop_column("periodic_tasks", "is_editable")
    op.drop_column("periodic_tasks", "is_locked")
    op.drop_column("periodic_tasks", "scope")
