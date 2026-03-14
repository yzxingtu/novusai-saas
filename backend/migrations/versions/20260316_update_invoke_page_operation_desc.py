"""update invoke_page_operation description to cover editor operations

Revision ID: 20260316_page_op_v3
Revises: 20260316_novusdoc_scope
Create Date: 2026-03-16 02:00:00.000000+00:00

"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260316_page_op_v3"
down_revision: str | Sequence[str] | None = "20260316_novusdoc_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INVOKE_PAGE_OPERATION_CONFIG = {
    "builtin_type": "page_operation",
    "tools": [
        {
            "name": "invoke_page_operation",
            "description": (
                "Execute a page operation on the user's current page via WebSocket. "
                "IMPORTANT: You MUST provide operation_name in EVERY call. "
                "Never omit operation_name — the call will fail without it.\n\n"
                "Supports multiple operation categories:\n"
                "- LIST/CRUD ops: refresh_list, search, clear_search, create_record, "
                "edit_record, navigate_to_detail, view_recycle_bin\n"
                "- FORM ops: get_form_state, fill_form, validate_form, get_form_options\n"
                "- EDITOR ops (rich text): get_editor_text, get_editor_html, get_selection, "
                "insert_content, replace_content, append_content, format_text, "
                "clear_formatting, set_heading, toggle_list, toggle_blockquote, "
                "toggle_code_block, set_text_align, manage_link, insert_table, "
                "select_all, undo, redo\n"
                "- DOCUMENT ops (NovusDoc): save_document, update_title, toggle_status, "
                "export_document\n\n"
                "FORM WORKFLOW — When user asks to create/edit a record:\n"
                "1. Call get_page_context to discover page_key and available operations\n"
                "2. Call create_record/edit_record to open the form\n"
                "3. Call get_form_state to see current field values\n"
                "4. Call fill_form to fill ALL fields based on context\n"
                "5. For remote_select fields, call get_form_options first\n"
                "6. User reviews the form and submits manually\n\n"
                "EDITOR WORKFLOW — When user asks to read/edit rich text:\n"
                "1. Call get_page_context (body excerpt in page_data.document_body_text)\n"
                "2. Call get_editor_text / get_editor_html for full content\n"
                "3. Call replace_content, insert_content, format_text, set_heading etc. "
                "to modify content"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page_key": {
                        "type": "string",
                        "description": "The page identifier (dot-notation, e.g. 'admin.ai.agents').",
                    },
                    "operation_name": {
                        "type": "string",
                        "description": (
                            "REQUIRED in every call. The operation to execute. "
                            "List ops: refresh_list, search, clear_search, create_record, "
                            "edit_record, navigate_to_detail, view_recycle_bin. "
                            "Form ops: get_form_state, fill_form, validate_form, get_form_options. "
                            "Editor ops: get_editor_text, get_editor_html, get_selection, "
                            "insert_content, replace_content, append_content, format_text, "
                            "clear_formatting, set_heading, toggle_list, toggle_blockquote, "
                            "toggle_code_block, set_text_align, manage_link, insert_table, "
                            "select_all, undo, redo. "
                            "Document ops: save_document, update_title, toggle_status, export_document."
                        ),
                    },
                    "params": {
                        "type": "object",
                        "description": (
                            "Operation parameters. For fill_form: field key-value pairs. "
                            "For replace_content/insert_content: {content: '...', format: 'text'|'html'}. "
                            "For format_text: {command: 'bold'|'italic'|'underline'|...}. "
                            "For set_heading: {level: 1|2|3}. For update_title: {title: '...'}."
                        ),
                        "default": {},
                    },
                },
                "required": ["page_key", "operation_name"],
            },
        }
    ],
}


def upgrade() -> None:
    conn = op.get_bind()

    row = conn.execute(
        text(
            "SELECT id FROM skills "
            "WHERE name = 'invoke_page_operation' AND type = 'builtin' "
            "AND tenant_id IS NULL AND is_system = true AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
    ).fetchone()
    if row:
        conn.execute(
            text(
                "UPDATE skills SET "
                "config = CAST(:config AS jsonb), "
                "updated_at = NOW() "
                "WHERE id = :skill_id"
            ),
            {
                "skill_id": row[0],
                "config": json.dumps(INVOKE_PAGE_OPERATION_CONFIG),
            },
        )
        print(f"[SEED] Updated invoke_page_operation skill (id={row[0]}) with editor-aware description.")


def downgrade() -> None:
    print("[SEED] Downgrade: no-op for invoke_page_operation description update.")
