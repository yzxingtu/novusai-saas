"""enhance page awareness tool descriptions for form-aware AI

Revision ID: 20260313_page_awareness_v2
Revises: 51e07931504d
Create Date: 2026-03-13 10:00:00.000000+00:00

"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260313_page_awareness_v2"
down_revision: str | Sequence[str] | None = "51e07931504d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Enhanced tool description for get_page_context
GET_PAGE_CONTEXT_CONFIG = {
    "builtin_type": "page_context",
    "tools": [
        {
            "name": "get_page_context",
            "description": (
                "Get the current page context including page identifier, title, entity info, "
                "form field schema (with component types, options, constraints), and available "
                "operations. Returns structured data about what the user is viewing, including "
                "form_fields with their component type (input/select/remote_select/switch/date/etc), "
                "static options, required status, and constraints. "
                "ALWAYS call this first before any page operation to understand the page structure."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    ],
}

# Enhanced tool description for invoke_page_operation
INVOKE_PAGE_OPERATION_CONFIG = {
    "builtin_type": "page_operation",
    "tools": [
        {
            "name": "invoke_page_operation",
            "description": (
                "Execute a page operation on the user's current page via WebSocket. "
                "Supports CRUD operations (refresh_list, search, create_record, edit_record) "
                "and form-aware operations (get_form_state, fill_form, validate_form, get_form_options). "
                "\n\n"
                "FORM WORKFLOW - When user asks to create/edit a record:\n"
                "1. Call get_page_context to discover page_key and available operations\n"
                "2. Call create_record/edit_record to open the form (can pre-fill known fields)\n"
                "3. Call get_form_state to see current field values and available fields\n"
                "4. Call fill_form to intelligently fill ALL fields based on context\n"
                "5. For remote_select fields, call get_form_options first to know available choices\n"
                "6. User reviews the form and submits manually\n\n"
                "IMPORTANT: When filling forms, try to fill ALL fields, not just the name. "
                "Use the field descriptors from get_page_context to understand each field's "
                "type, options, and constraints. For select fields, use exact option values."
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
                            "The operation to execute. Standard ops: refresh_list, search, "
                            "clear_search, create_record, edit_record, navigate_to_detail, "
                            "view_recycle_bin. Form ops: get_form_state, fill_form, "
                            "validate_form, get_form_options."
                        ),
                    },
                    "params": {
                        "type": "object",
                        "description": (
                            "Operation parameters. For fill_form: field key-value pairs "
                            "matching the form schema. For get_form_options: {field_name: '<name>'}. "
                            "For search: filter key-value pairs."
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

    # Update get_page_context skill config
    row = conn.execute(
        text(
            "SELECT id FROM skills "
            "WHERE name = 'get_page_context' AND type = 'builtin' "
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
                "config": json.dumps(GET_PAGE_CONTEXT_CONFIG),
            },
        )
        print(f"[SEED] Updated get_page_context skill (id={row[0]}) with enhanced description.")

    # Update invoke_page_operation skill config
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
        print(f"[SEED] Updated invoke_page_operation skill (id={row[0]}) with enhanced description.")


def downgrade() -> None:
    print("[SEED] Downgrade: no-op for enhanced page awareness tool descriptions.")
