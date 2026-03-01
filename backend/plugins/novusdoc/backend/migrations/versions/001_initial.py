"""NovusDoc plugin initial tables

Revision ID: novusdoc_001
Revises:
Create Date: 2026-02-25

Creates:
- px_novusdoc_folders
- px_novusdoc_documents
- px_novusdoc_tags
- px_novusdoc_doc_tags
- GIN full-text search index on documents.content_text
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "novusdoc_001"
down_revision = None
branch_labels = ("plugin_novusdoc",)
depends_on = None


def upgrade() -> None:
    # ── px_novusdoc_folders ──
    op.create_table(
        "px_novusdoc_folders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("px_novusdoc_folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_novusdoc_folders_tenant_parent",
        "px_novusdoc_folders",
        ["tenant_id", "parent_id"],
    )

    # ── px_novusdoc_documents ──
    op.create_table(
        "px_novusdoc_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("px_novusdoc_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("creator_type", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_starred", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cover_image", sa.String(500), nullable=True),
        sa.Column("last_edited_by", sa.Integer(), nullable=True),
        sa.Column("last_edited_at", sa.String(50), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_novusdoc_docs_tenant_folder",
        "px_novusdoc_documents",
        ["tenant_id", "folder_id"],
    )
    op.create_index(
        "ix_novusdoc_docs_tenant_status",
        "px_novusdoc_documents",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_novusdoc_docs_creator",
        "px_novusdoc_documents",
        ["creator_id", "creator_type"],
    )
    op.create_index(
        "ix_novusdoc_docs_starred",
        "px_novusdoc_documents",
        ["tenant_id", "is_starred"],
    )
    # GIN full-text search index (simple config for CJK compatibility)
    op.execute(
        "CREATE INDEX ix_novusdoc_docs_search "
        "ON px_novusdoc_documents "
        "USING gin(to_tsvector('simple', coalesce(content_text, '')))"
    )

    # ── px_novusdoc_tags ──
    op.create_table(
        "px_novusdoc_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_novusdoc_tag_tenant_name",
        "px_novusdoc_tags",
        ["tenant_id", "name"],
    )

    # ── px_novusdoc_doc_tags ──
    op.create_table(
        "px_novusdoc_doc_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("px_novusdoc_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("px_novusdoc_tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_novusdoc_doc_tag",
        "px_novusdoc_doc_tags",
        ["document_id", "tag_id"],
    )
    op.create_index("ix_novusdoc_doc_tags_doc", "px_novusdoc_doc_tags", ["document_id"])
    op.create_index("ix_novusdoc_doc_tags_tag", "px_novusdoc_doc_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_table("px_novusdoc_doc_tags")
    op.drop_table("px_novusdoc_tags")
    op.execute("DROP INDEX IF EXISTS ix_novusdoc_docs_search")
    op.drop_table("px_novusdoc_documents")
    op.drop_table("px_novusdoc_folders")
