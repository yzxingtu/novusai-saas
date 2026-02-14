"""add_global_scope

Add 'global' as a valid scope value for skill_packages and skills.
Update system data intelligence package/skill scope to 'global'.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-02-14 20:20:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update system data intelligence package + skill scope to 'global'."""
    conn = op.get_bind()

    # Update system data intelligence skill package
    conn.execute(text(
        "UPDATE skill_packages SET scope = 'global' "
        "WHERE name = '系统数据智能技能包' AND is_system = true"
    ))

    # Update system data intelligence skill
    conn.execute(text(
        "UPDATE skills SET scope = 'global' "
        "WHERE name = '平台数据管理' AND is_system = true "
        "AND type = 'data_intelligence'"
    ))

    print("[MIGRATION] Updated system data intelligence scope to 'global'")


def downgrade() -> None:
    """Revert scope back to 'admin'."""
    conn = op.get_bind()

    conn.execute(text(
        "UPDATE skill_packages SET scope = 'admin' "
        "WHERE name = '系统数据智能技能包' AND is_system = true"
    ))

    conn.execute(text(
        "UPDATE skills SET scope = 'admin' "
        "WHERE name = '平台数据管理' AND is_system = true "
        "AND type = 'data_intelligence'"
    ))

    print("[MIGRATION] Reverted system data intelligence scope to 'admin'")
