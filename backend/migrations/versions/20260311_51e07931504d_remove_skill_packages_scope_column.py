"""remove skill_packages scope column

Revision ID: 51e07931504d
Revises: 20260310_drop_kb_ids
Create Date: 2026-03-11 19:28:01.438907+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51e07931504d'
down_revision: Union[str, None] = '20260310_drop_kb_ids'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM resource_tenant_assignments "
        "WHERE resource_type = 'skill_package'"
    )

    op.drop_index("ix_skill_packages_tenant_scope", table_name="skill_packages")
    op.drop_index("ix_skill_packages_scope", table_name="skill_packages")
    op.drop_column("skill_packages", "scope")


def downgrade() -> None:
    op.add_column(
        "skill_packages",
        sa.Column(
            "scope",
            sa.String(20),
            nullable=False,
            server_default="admin_and_all",
        ),
    )
    op.create_index("ix_skill_packages_scope", "skill_packages", ["scope"])
    op.create_index(
        "ix_skill_packages_tenant_scope",
        "skill_packages",
        ["tenant_id", "scope"],
    )
