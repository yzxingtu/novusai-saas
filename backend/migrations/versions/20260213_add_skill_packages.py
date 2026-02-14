"""add_skill_packages

Create skill_packages table and add package_id FK to skills.
Migrate existing skills: each skill gets wrapped in its own package.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-13 22:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create skill_packages table
    op.create_table(
        'skill_packages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True, comment='租户ID（scope=tenant 时必填，scope=admin 时为 NULL）'),
        sa.Column('name', sa.String(100), nullable=False, comment='技能包名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='技能包描述'),
        sa.Column('avatar', sa.String(255), nullable=True, comment='技能包图标'),
        sa.Column('scope', sa.String(20), nullable=False, server_default='tenant', comment='作用域'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='启用状态'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('0'), comment='排序'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('delete_level', sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_skill_packages_id', 'skill_packages', ['id'])
    op.create_index('ix_skill_packages_name', 'skill_packages', ['name'])
    op.create_index('ix_skill_packages_tenant_id', 'skill_packages', ['tenant_id'])
    op.create_index('ix_skill_packages_scope', 'skill_packages', ['scope'])
    op.create_index('ix_skill_packages_is_deleted', 'skill_packages', ['is_deleted'])
    op.create_index('ix_skill_packages_tenant_scope', 'skill_packages', ['tenant_id', 'scope'])
    op.create_index('ix_skill_packages_tenant_active', 'skill_packages', ['tenant_id', 'is_active'])

    # 2. Add package_id column to skills (nullable first for data migration)
    op.add_column('skills', sa.Column('package_id', sa.Integer(), nullable=True))

    # 3. Data migration: wrap each existing skill in its own package
    conn = op.get_bind()
    skills = conn.execute(text(
        "SELECT id, tenant_id, name, description, avatar, scope, is_active, "
        "sort_order, created_at, updated_at, is_deleted, deleted_at, delete_level "
        "FROM skills ORDER BY id"
    )).fetchall()

    for skill in skills:
        # Create a package for this skill
        result = conn.execute(text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, avatar, scope, is_active, sort_order, "
            " created_at, updated_at, is_deleted, deleted_at, delete_level) "
            "VALUES "
            "(:tenant_id, :name, :description, :avatar, :scope, :is_active, :sort_order, "
            " :created_at, :updated_at, :is_deleted, :deleted_at, :delete_level) "
            "RETURNING id"
        ), {
            "tenant_id": skill.tenant_id,
            "name": skill.name,
            "description": skill.description,
            "avatar": skill.avatar,
            "scope": skill.scope,
            "is_active": skill.is_active,
            "sort_order": skill.sort_order,
            "created_at": skill.created_at,
            "updated_at": skill.updated_at,
            "is_deleted": skill.is_deleted,
            "deleted_at": skill.deleted_at,
            "delete_level": skill.delete_level,
        })
        pkg_id = result.fetchone()[0]

        # Update skill to reference the new package
        conn.execute(text(
            "UPDATE skills SET package_id = :pkg_id WHERE id = :skill_id"
        ), {"pkg_id": pkg_id, "skill_id": skill.id})

    print(f"[MIGRATE] Wrapped {len(skills)} existing skills into packages.")

    # 4. Make package_id NOT NULL + add FK + index
    op.alter_column('skills', 'package_id', nullable=False)
    op.create_foreign_key(
        'fk_skills_package_id',
        'skills', 'skill_packages',
        ['package_id'], ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_skills_package', 'skills', ['package_id'])


def downgrade() -> None:
    # Remove FK and column
    op.drop_index('ix_skills_package', table_name='skills')
    op.drop_constraint('fk_skills_package_id', 'skills', type_='foreignkey')
    op.drop_column('skills', 'package_id')

    # Drop skill_packages table
    op.drop_index('ix_skill_packages_tenant_active', table_name='skill_packages')
    op.drop_index('ix_skill_packages_tenant_scope', table_name='skill_packages')
    op.drop_index('ix_skill_packages_is_deleted', table_name='skill_packages')
    op.drop_index('ix_skill_packages_scope', table_name='skill_packages')
    op.drop_index('ix_skill_packages_tenant_id', table_name='skill_packages')
    op.drop_index('ix_skill_packages_name', table_name='skill_packages')
    op.drop_index('ix_skill_packages_id', table_name='skill_packages')
    op.drop_table('skill_packages')
