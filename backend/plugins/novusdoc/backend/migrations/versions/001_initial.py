"""create novusdoc tables / 创建

Revision ID: novusdoc_001_init
Revises:
Create Date: 2026-03-15

branch_labels = ('plugin_novusdoc',)"""
import sqlalchemy as sa
from alembic import op

revision = 'novusdoc_001_init'
down_revision = None
branch_labels = ('plugin_novusdoc',)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'px_novusdoc_folders' not in existing_tables:
        op.create_table(
            'px_novusdoc_folders',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('name', sa.String(200), nullable=False),
            sa.Column('parent_id', sa.Integer(),
                      sa.ForeignKey('px_novusdoc_folders.id', ondelete='CASCADE'),
                      nullable=True, index=True),
            sa.Column('sort_order', sa.Integer(), nullable=False, default=0),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False, index=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('delete_level', sa.String(20), nullable=True),
        )

    if 'px_novusdoc_documents' not in existing_tables:
        op.create_table(
            'px_novusdoc_documents',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('folder_id', sa.Integer(),
                      sa.ForeignKey('px_novusdoc_folders.id', ondelete='SET NULL'),
                      nullable=True, index=True),
            sa.Column('title', sa.String(500), nullable=False, default='Untitled'),
            sa.Column('content', sa.JSON(), nullable=True, comment='Tiptap JSON content'),
            sa.Column('content_text', sa.Text(), nullable=True, comment='Plain text for search'),
            sa.Column('content_html', sa.Text(), nullable=True, comment='HTML export cache'),
            sa.Column('word_count', sa.Integer(), nullable=False, default=0),
            sa.Column('status', sa.String(20), nullable=False, default='draft'),
            sa.Column('is_pinned', sa.Boolean(), nullable=False, default=False),
            sa.Column('cover_image', sa.String(500), nullable=True),
            sa.Column('created_by', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False, index=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('delete_level', sa.String(20), nullable=True),
        )

    if 'px_novusdoc_tags' not in existing_tables:
        op.create_table(
            'px_novusdoc_tags',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('tenant_id', sa.Integer(),
                      sa.ForeignKey('tenants.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('color', sa.String(20), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False, index=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('delete_level', sa.String(20), nullable=True),
        )

    if 'px_novusdoc_document_tags' not in existing_tables:
        op.create_table(
            'px_novusdoc_document_tags',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('document_id', sa.Integer(),
                      sa.ForeignKey('px_novusdoc_documents.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('tag_id', sa.Integer(),
                      sa.ForeignKey('px_novusdoc_tags.id', ondelete='CASCADE'),
                      nullable=False, index=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False, index=True),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.Column('delete_level', sa.String(20), nullable=True),
        )


def downgrade():
    op.drop_table('px_novusdoc_document_tags')
    op.drop_table('px_novusdoc_tags')
    op.drop_table('px_novusdoc_documents')
    op.drop_table('px_novusdoc_folders')
