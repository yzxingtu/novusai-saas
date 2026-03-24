"""add novusdoc folder/tag owner fields

Revision ID: novusdoc_003_folder_tag_owner
Revises: novusdoc_002_tid_nullable
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op


revision = "novusdoc_003_folder_tag_owner"
down_revision = "novusdoc_002_tid_nullable"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "px_novusdoc_folders",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_px_novusdoc_folders_created_by",
        "px_novusdoc_folders",
        ["created_by"],
        unique=False,
    )

    op.add_column(
        "px_novusdoc_tags",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_px_novusdoc_tags_created_by",
        "px_novusdoc_tags",
        ["created_by"],
        unique=False,
    )

    op.execute(
        """
        UPDATE px_novusdoc_folders AS folder
        SET created_by = source.created_by
        FROM (
            SELECT folder_id, MAX(created_by) AS created_by
            FROM px_novusdoc_documents
            WHERE folder_id IS NOT NULL
              AND created_by IS NOT NULL
            GROUP BY folder_id
        ) AS source
        WHERE folder.id = source.folder_id
          AND folder.created_by IS NULL
        """
    )

    op.execute(
        """
        UPDATE px_novusdoc_tags AS tag
        SET created_by = source.created_by
        FROM (
            SELECT rel.tag_id, MAX(doc.created_by) AS created_by
            FROM px_novusdoc_document_tags AS rel
            JOIN px_novusdoc_documents AS doc
              ON doc.id = rel.document_id
            WHERE doc.created_by IS NOT NULL
            GROUP BY rel.tag_id
        ) AS source
        WHERE tag.id = source.tag_id
          AND tag.created_by IS NULL
        """
    )


def downgrade():
    op.drop_index(
        "ix_px_novusdoc_tags_created_by",
        table_name="px_novusdoc_tags",
    )
    op.drop_column("px_novusdoc_tags", "created_by")

    op.drop_index(
        "ix_px_novusdoc_folders_created_by",
        table_name="px_novusdoc_folders",
    )
    op.drop_column("px_novusdoc_folders", "created_by")
