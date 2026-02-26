"""NovusDoc Pro plugin initial tables (collaboration)

Revision ID: novusdoc_pro_001
Revises:
Create Date: 2026-02-25

Creates:
- px_novusdoc_pro_doc_members
- px_novusdoc_pro_versions
- px_novusdoc_pro_comments
- px_novusdoc_pro_comment_replies
- px_novusdoc_pro_shares
- px_novusdoc_pro_templates
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "novusdoc_pro_001"
down_revision = None
branch_labels = ("plugin_novusdoc_pro",)
depends_on = None


def upgrade() -> None:
    # ── px_novusdoc_pro_doc_members ──
    op.create_table(
        "px_novusdoc_pro_doc_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_type", sa.String(20), nullable=False, server_default="tenant_admin"),
        sa.Column("role", sa.String(20), nullable=False, server_default="editor"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_ndpro_doc_member", "px_novusdoc_pro_doc_members", ["document_id", "user_id"])
    op.create_index("ix_ndpro_members_doc", "px_novusdoc_pro_doc_members", ["document_id", "tenant_id"])

    # ── px_novusdoc_pro_versions ──
    op.create_table(
        "px_novusdoc_pro_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("creator_name", sa.String(100), nullable=True),
        sa.Column("version_note", sa.String(500), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── px_novusdoc_pro_comments ──
    op.create_table(
        "px_novusdoc_pro_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("creator_name", sa.String(100), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("anchor_from", sa.Integer(), nullable=True),
        sa.Column("anchor_to", sa.Integer(), nullable=True),
        sa.Column("quoted_text", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ndpro_comments_doc", "px_novusdoc_pro_comments", ["document_id", "tenant_id"])

    # ── px_novusdoc_pro_comment_replies ──
    op.create_table(
        "px_novusdoc_pro_comment_replies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column(
            "comment_id", sa.Integer(),
            sa.ForeignKey("px_novusdoc_pro_comments.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("creator_name", sa.String(100), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── px_novusdoc_pro_shares ──
    op.create_table(
        "px_novusdoc_pro_shares",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("document_id", sa.Integer(), nullable=False, index=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("permission", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("expires_at", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # ── px_novusdoc_pro_templates ──
    op.create_table(
        "px_novusdoc_pro_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("content", postgresql.JSONB(), nullable=True),
        sa.Column("cover_image", sa.String(500), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creator_id", sa.Integer(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false", index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("px_novusdoc_pro_templates")
    op.drop_table("px_novusdoc_pro_shares")
    op.drop_table("px_novusdoc_pro_comment_replies")
    op.drop_table("px_novusdoc_pro_comments")
    op.drop_table("px_novusdoc_pro_versions")
    op.drop_table("px_novusdoc_pro_doc_members")
