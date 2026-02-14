"""refactor agent_skill_bindings: skill_id → package_id, drop scope from skills

1. Add package_id column to agent_skill_bindings (nullable initially)
2. Data migration: populate package_id from skill.package_id
3. Drop skill_id column and old unique constraint
4. Make package_id NOT NULL, add new unique constraint
5. Drop scope column and related index from skills table

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-02-15 00:00:00.000000+08:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ========================================
    # 1. agent_skill_bindings: skill_id → package_id
    # ========================================

    # 1a. Add package_id column (nullable initially)
    op.add_column(
        'agent_skill_bindings',
        sa.Column('package_id', sa.Integer(), nullable=True, comment='技能包ID'),
    )

    # 1b. Data migration: populate package_id from skills.package_id
    conn.execute(sa.text("""
        UPDATE agent_skill_bindings AS b
        SET package_id = s.package_id
        FROM skills AS s
        WHERE b.skill_id = s.id
    """))

    # 1c. Delete orphan bindings where skill no longer exists
    conn.execute(sa.text("""
        DELETE FROM agent_skill_bindings
        WHERE package_id IS NULL
    """))

    # 1d. Deduplicate: if same agent binds multiple skills from same package,
    #     keep only the one with lowest sort_order
    conn.execute(sa.text("""
        DELETE FROM agent_skill_bindings
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM agent_skill_bindings
            GROUP BY agent_id, package_id
        )
    """))

    # 1e. Drop old unique constraint and skill_id column
    op.drop_constraint('uq_agent_skill_binding', 'agent_skill_bindings', type_='unique')
    op.drop_column('agent_skill_bindings', 'skill_id')

    # 1f. Make package_id NOT NULL
    op.alter_column('agent_skill_bindings', 'package_id', nullable=False)

    # 1g. Add FK constraint and new unique constraint
    op.create_foreign_key(
        'fk_agent_skill_bindings_package_id',
        'agent_skill_bindings', 'skill_packages',
        ['package_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_unique_constraint(
        'uq_agent_skill_package_binding',
        'agent_skill_bindings',
        ['agent_id', 'package_id'],
    )
    op.create_index(
        'ix_agent_skill_bindings_package_id',
        'agent_skill_bindings',
        ['package_id'],
    )

    # ========================================
    # 2. skills: drop scope column and related index
    # ========================================

    # 2a. Drop indexes that reference scope
    op.drop_index('ix_skills_tenant_scope', table_name='skills')
    op.drop_index('ix_skills_scope', table_name='skills')

    # 2b. Drop scope column
    op.drop_column('skills', 'scope')


def downgrade() -> None:
    # ========================================
    # Reverse: restore scope to skills, restore skill_id to bindings
    # ========================================

    # 1. Restore scope column to skills
    op.add_column(
        'skills',
        sa.Column('scope', sa.String(20), nullable=False, server_default='tenant',
                   comment='作用域'),
    )
    op.create_index('ix_skills_tenant_scope', 'skills', ['tenant_id', 'scope'])
    op.create_index('ix_skills_scope', 'skills', ['scope'])

    # Populate scope from parent package
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE skills AS s
        SET scope = sp.scope
        FROM skill_packages AS sp
        WHERE s.package_id = sp.id
    """))

    # 2. Restore skill_id to agent_skill_bindings
    # Drop new constraints first
    op.drop_index('ix_agent_skill_bindings_package_id', table_name='agent_skill_bindings')
    op.drop_constraint('uq_agent_skill_package_binding', 'agent_skill_bindings', type_='unique')
    op.drop_constraint('fk_agent_skill_bindings_package_id', 'agent_skill_bindings', type_='foreignkey')

    # Add skill_id back (nullable)
    op.add_column(
        'agent_skill_bindings',
        sa.Column('skill_id', sa.Integer(), nullable=True, comment='技能ID'),
    )

    # NOTE: We cannot perfectly restore skill_id since the mapping was many-to-one.
    # Set skill_id to the first active skill in the package as best-effort.
    conn.execute(sa.text("""
        UPDATE agent_skill_bindings AS b
        SET skill_id = (
            SELECT s.id FROM skills s
            WHERE s.package_id = b.package_id
              AND s.is_deleted = false
              AND s.is_active = true
            ORDER BY s.sort_order
            LIMIT 1
        )
    """))

    # Delete bindings that couldn't be mapped
    conn.execute(sa.text("""
        DELETE FROM agent_skill_bindings WHERE skill_id IS NULL
    """))

    op.alter_column('agent_skill_bindings', 'skill_id', nullable=False)
    op.create_foreign_key(
        'fk_agent_skill_bindings_skill_id',
        'agent_skill_bindings', 'skills',
        ['skill_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_unique_constraint(
        'uq_agent_skill_binding',
        'agent_skill_bindings',
        ['agent_id', 'skill_id'],
    )

    # Drop package_id
    op.drop_column('agent_skill_bindings', 'package_id')
