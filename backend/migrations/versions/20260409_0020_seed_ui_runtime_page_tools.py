"""seed UI runtime page tools and retire legacy page awareness tools

Revision ID: 20260409_ui_runtime_page_tools
Revises: 20260405_log_identity_snapshots
Create Date: 2026-04-09
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import MetaData, Table, and_, bindparam, func, inspect, or_, select

revision: str = "20260409_ui_runtime_page_tools"
down_revision: str | Sequence[str] | None = "20260405_log_identity_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PACKAGE_NAME = "页面感知交互"
PACKAGE_DESCRIPTION = (
    "UI Runtime 页面交互能力包。提供 ui_get_snapshot、ui_read_region、"
    "ui_read_table、ui_list_interactables、ui_click、ui_open_surface、"
    "ui_get_form_state、ui_set_field、ui_fill_form、ui_submit_form 等工具，"
    "供智能体在 thin page context 基础上按需读取、点击与填写页面。"
)

LEGACY_SKILL_NAMES = (
    "get_page_context",
    "invoke_page_operation",
)
LEGACY_SKILL_PREFIXES = ("pageop_",)

UI_RUNTIME_SKILLS: list[dict[str, object]] = [
    {
        "name": "ui_get_snapshot",
        "description": (
            "Get a UI Runtime snapshot for the current page session. Use compact mode "
            "for the default thin structural view and full mode only when more detail is needed."
        ),
        "timeout": 20,
        "sort_order": 10,
        "config": {
            "builtin_type": "ui_snapshot",
            "tools": [
                {
                    "name": "ui_get_snapshot",
                    "description": (
                        "Get the current UI Runtime snapshot for the page. Prefer mode='compact' "
                        "for a thin structural summary; use mode='full' only when you need deeper detail."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "mode": {
                                "type": "string",
                                "enum": ["compact", "full"],
                                "description": "Snapshot detail level. Defaults to compact.",
                            },
                            "expected_ui_epoch": {
                                "type": "integer",
                                "description": "Optional UI epoch hint from the previous result.",
                            },
                        },
                        "required": [],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_read_region",
        "description": (
            "Read a specific visible region from the current UI Runtime surface."
        ),
        "timeout": 20,
        "sort_order": 20,
        "config": {
            "builtin_type": "ui_read",
            "tools": [
                {
                    "name": "ui_read_region",
                    "description": (
                        "Read a specific region by locator from the current page surface."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "region_locator": {
                                "type": "string",
                                "description": "Stable locator or semantic locator for the region to read.",
                            }
                        },
                        "required": ["region_locator"],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_read_table",
        "description": (
            "Read visible table data from the current page with pagination-aware parameters."
        ),
        "timeout": 25,
        "sort_order": 30,
        "config": {
            "builtin_type": "ui_read",
            "tools": [
                {
                    "name": "ui_read_table",
                    "description": (
                        "Read structured data from a table on the current page. "
                        "Use page/page_size to keep results narrow."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_locator": {
                                "type": "string",
                                "description": "Stable locator or semantic locator for the table.",
                            },
                            "page": {
                                "type": "integer",
                                "description": "Optional page number to read.",
                            },
                            "page_size": {
                                "type": "integer",
                                "description": "Optional page size override.",
                            },
                            "filters": {
                                "type": "object",
                                "description": "Optional read-time filter hints.",
                                "default": {},
                            },
                        },
                        "required": ["table_locator"],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_list_interactables",
        "description": (
            "List actionable interactables on the active surface or a specific surface."
        ),
        "timeout": 20,
        "sort_order": 40,
        "config": {
            "builtin_type": "ui_read",
            "tools": [
                {
                    "name": "ui_list_interactables",
                    "description": (
                        "List buttons, links, menu items, tabs and other interactables available on a surface."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "surface_id": {
                                "type": "string",
                                "description": "Optional target surface id. Defaults to the active surface.",
                            }
                        },
                        "required": [],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_click",
        "description": "Click a UI element identified by locator on the current page.",
        "timeout": 30,
        "sort_order": 50,
        "config": {
            "builtin_type": "ui_action",
            "tools": [
                {
                    "name": "ui_click",
                    "description": (
                        "Click a button, link, menu item, tab or pagination target identified by locator."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_locator": {
                                "type": "string",
                                "description": "Stable locator or semantic locator for the click target.",
                            },
                            "confirm": {
                                "type": "boolean",
                                "description": "Whether the model is explicitly confirming a risky action.",
                            },
                        },
                        "required": ["target_locator"],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_open_surface",
        "description": "Open a drawer, modal, dropdown or other surface by locator.",
        "timeout": 30,
        "sort_order": 60,
        "config": {
            "builtin_type": "ui_action",
            "tools": [
                {
                    "name": "ui_open_surface",
                    "description": (
                        "Open a surface such as a drawer, modal, dropdown or popover by locator."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "surface_type": {
                                "type": "string",
                                "enum": ["drawer", "dropdown", "modal", "popover", "unknown"],
                                "description": "Optional expected surface type.",
                            },
                            "target_locator": {
                                "type": "string",
                                "description": "Locator for the trigger element that opens the surface.",
                            },
                            "confirm": {
                                "type": "boolean",
                                "description": "Whether the action is explicitly confirmed.",
                            },
                        },
                        "required": ["target_locator"],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_get_form_state",
        "description": "Inspect the active form session or a specific form session.",
        "timeout": 20,
        "sort_order": 70,
        "config": {
            "builtin_type": "ui_form",
            "tools": [
                {
                    "name": "ui_get_form_state",
                    "description": (
                        "Get current form session mode, stage, fields and remaining required fields."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "form_session_id": {
                                "type": "string",
                                "description": "Optional target form session id. Defaults to the active form.",
                            }
                        },
                        "required": [],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_set_field",
        "description": "Set a single field value in the active or specified form session.",
        "timeout": 25,
        "sort_order": 80,
        "config": {
            "builtin_type": "ui_form",
            "tools": [
                {
                    "name": "ui_set_field",
                    "description": "Set one field value in a form session.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "form_session_id": {
                                "type": "string",
                                "description": "Optional target form session id.",
                            },
                            "field_name": {
                                "type": "string",
                                "description": "Field name to set.",
                            },
                            "value": {
                                "description": "Field value to write.",
                            },
                        },
                        "required": ["field_name", "value"],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_fill_form",
        "description": "Fill multiple form fields in one call for the active form session.",
        "timeout": 35,
        "sort_order": 90,
        "config": {
            "builtin_type": "ui_form",
            "tools": [
                {
                    "name": "ui_fill_form",
                    "description": (
                        "Fill multiple form fields at once and return validation hints plus remaining required fields."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "form_session_id": {
                                "type": "string",
                                "description": "Optional target form session id.",
                            },
                            "fields": {
                                "type": "object",
                                "description": "Field name to value mapping.",
                                "default": {},
                            },
                            "validate_only": {
                                "type": "boolean",
                                "description": "If true, validate without committing changes.",
                            },
                        },
                        "required": ["fields"],
                    },
                }
            ],
        },
    },
    {
        "name": "ui_submit_form",
        "description": "Submit the active form session or a specified form session.",
        "timeout": 45,
        "sort_order": 100,
        "config": {
            "builtin_type": "ui_form",
            "tools": [
                {
                    "name": "ui_submit_form",
                    "description": (
                        "Submit a form session. Use confirm=true only after the user or runtime explicitly allows submission."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "form_session_id": {
                                "type": "string",
                                "description": "Optional target form session id.",
                            },
                            "confirm": {
                                "type": "boolean",
                                "description": "Explicit confirmation flag for risky submission.",
                            },
                        },
                        "required": [],
                    },
                }
            ],
        },
    },
]


def _table_columns(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return set()
    return {
        str(column["name"])
        for column in inspector.get_columns(table_name)
        if column.get("name")
    }


def _reflect_table(conn, table_name: str) -> Table:
    return Table(table_name, MetaData(), autoload_with=conn)


def _filter_supported_update_values(table: Table, values: dict[str, object]) -> dict[str, object]:
    """Drop enum values that are not accepted by the current DB schema."""
    filtered: dict[str, object] = {}
    for key, value in values.items():
        column = table.c.get(key)
        if column is None:
            continue
        enum_values = getattr(column.type, "enums", None)
        if enum_values and isinstance(value, str) and value not in enum_values:
            continue
        filtered[key] = value
    return filtered


def _package_seed_values(
    columns: set[str],
    *,
    include_created_at: bool,
) -> dict[str, object]:
    values: dict[str, object] = {}
    if "tenant_id" in columns:
        values["tenant_id"] = None
    if "name" in columns:
        values["name"] = PACKAGE_NAME
    if "description" in columns:
        values["description"] = PACKAGE_DESCRIPTION
    if "is_system" in columns:
        values["is_system"] = True
    if "is_active" in columns:
        values["is_active"] = True
    if "sort_order" in columns:
        values["sort_order"] = 4
    if "is_deleted" in columns:
        values["is_deleted"] = False
    if "scope" in columns:
        values["scope"] = "global_shared"
    if "bind_mode" in columns:
        values["bind_mode"] = "manual"
    if "target_audience" in columns:
        values["target_audience"] = "admin_tenant"
    if "is_recommended" in columns:
        values["is_recommended"] = True
    if include_created_at and "created_at" in columns:
        values["created_at"] = func.now()
    if "updated_at" in columns:
        values["updated_at"] = func.now()
    return values


def _find_package(conn) -> int | None:
    columns = _table_columns(conn, "skill_packages")
    if not columns or "id" not in columns or "name" not in columns:
        return None
    skill_packages = _reflect_table(conn, "skill_packages")

    predicates = [skill_packages.c.name == bindparam("name")]
    if "tenant_id" in columns:
        predicates.append(skill_packages.c.tenant_id.is_(None))
    if "is_system" in columns:
        predicates.append(skill_packages.c.is_system.is_(True))
    if "is_deleted" in columns:
        predicates.append(skill_packages.c.is_deleted.is_(False))

    stmt = (
        select(skill_packages.c.id)
        .where(and_(*predicates))
        .order_by(skill_packages.c.id)
        .limit(1)
    )
    row = conn.execute(stmt, {"name": PACKAGE_NAME}).fetchone()
    return int(row[0]) if row else None


def _create_package(conn) -> int:
    columns = _table_columns(conn, "skill_packages")
    if not columns or "name" not in columns:
        raise RuntimeError("skill_packages.name is required for UI runtime package seed")

    skill_packages = _reflect_table(conn, "skill_packages")
    values = _package_seed_values(columns, include_created_at=True)
    values = _filter_supported_update_values(skill_packages, values)
    if not values or "name" not in values:
        raise RuntimeError("skill_packages.name is required after enum filtering")
    stmt = skill_packages.insert().values(**values)

    if "id" in columns:
        row = conn.execute(stmt.returning(skill_packages.c.id)).fetchone()
        if row:
            return int(row[0])
    else:
        conn.execute(stmt)

    package_id = _find_package(conn)
    if package_id is None:
        raise RuntimeError("failed to locate UI runtime package after insert")
    return package_id


def _sync_package(conn, package_id: int) -> None:
    columns = _table_columns(conn, "skill_packages")
    if not columns or "id" not in columns:
        return

    values = _package_seed_values(columns, include_created_at=False)
    if not values:
        return

    skill_packages = _reflect_table(conn, "skill_packages")
    values = _filter_supported_update_values(skill_packages, values)
    if not values:
        return
    stmt = (
        skill_packages.update()
        .where(skill_packages.c.id == bindparam("target_id"))
        .values(**values)
    )
    conn.execute(stmt, {"target_id": package_id})


def _find_skill(conn, name: str) -> int | None:
    columns = _table_columns(conn, "skills")
    if not columns or "id" not in columns or "name" not in columns:
        return None

    skills = _reflect_table(conn, "skills")
    predicates = [skills.c.name == bindparam("name")]
    if "type" in columns:
        predicates.append(skills.c.type == "builtin")
    if "tenant_id" in columns:
        predicates.append(skills.c.tenant_id.is_(None))
    if "is_system" in columns:
        predicates.append(skills.c.is_system.is_(True))
    if "is_deleted" in columns:
        predicates.append(skills.c.is_deleted.is_(False))

    stmt = select(skills.c.id).where(and_(*predicates)).order_by(skills.c.id).limit(1)
    row = conn.execute(stmt, {"name": name}).fetchone()
    return int(row[0]) if row else None


def _soft_delete_legacy_skills(conn) -> None:
    columns = _table_columns(conn, "skills")
    if not columns or "name" not in columns:
        return

    skills = _reflect_table(conn, "skills")
    values: dict[str, object] = {}
    if "is_active" in columns:
        values["is_active"] = False
    if "is_deleted" in columns:
        values["is_deleted"] = True
    if "updated_at" in columns:
        values["updated_at"] = func.now()
    if "deleted_at" in columns and "is_deleted" in columns:
        values["deleted_at"] = func.coalesce(skills.c.deleted_at, func.now())

    if not values:
        return

    legacy_predicates = [
        skills.c.name.in_(bindparam("legacy_names", expanding=True))
    ]
    prefix_params: dict[str, object] = {}
    for idx, prefix in enumerate(LEGACY_SKILL_PREFIXES):
        param_name = f"legacy_prefix_{idx}"
        legacy_predicates.append(skills.c.name.like(bindparam(param_name)))
        prefix_params[param_name] = f"{prefix}%"

    where_clauses = [or_(*legacy_predicates)]
    if "type" in columns:
        where_clauses.append(skills.c.type == "builtin")
    if "tenant_id" in columns:
        where_clauses.append(skills.c.tenant_id.is_(None))

    stmt = skills.update().where(and_(*where_clauses)).values(**values)
    conn.execute(
        stmt,
        {
            "legacy_names": list(LEGACY_SKILL_NAMES),
            **prefix_params,
        },
    )


def _upsert_skill(conn, package_id: int, skill_payload: dict[str, object]) -> None:
    columns = _table_columns(conn, "skills")
    if not columns or "name" not in columns:
        return

    skills = _reflect_table(conn, "skills")
    skill_id = _find_skill(conn, str(skill_payload["name"]))

    config_value: object = skill_payload["config"]
    if "config" in columns and "json" not in str(skills.c.config.type).lower():
        config_value = json.dumps(skill_payload["config"])

    payload: dict[str, object] = {}
    if "tenant_id" in columns:
        payload["tenant_id"] = None
    if "package_id" in columns:
        payload["package_id"] = package_id
    if "name" in columns:
        payload["name"] = str(skill_payload["name"])
    if "description" in columns:
        payload["description"] = str(skill_payload["description"])
    if "type" in columns:
        payload["type"] = "builtin"
    if "config" in columns:
        payload["config"] = config_value
    if "timeout" in columns:
        payload["timeout"] = int(skill_payload["timeout"])
    if "sort_order" in columns:
        payload["sort_order"] = int(skill_payload["sort_order"])
    if "is_system" in columns:
        payload["is_system"] = True
    if "is_active" in columns:
        payload["is_active"] = True
    if "is_deleted" in columns:
        payload["is_deleted"] = False

    if skill_id is None:
        insert_payload = dict(payload)
        if "created_at" in columns:
            insert_payload["created_at"] = func.now()
        if "updated_at" in columns:
            insert_payload["updated_at"] = func.now()
        if not insert_payload:
            return
        conn.execute(skills.insert().values(**insert_payload))
        return

    if "id" not in columns:
        return
    update_payload = dict(payload)
    if "updated_at" in columns:
        update_payload["updated_at"] = func.now()
    if not update_payload:
        return
    stmt = skills.update().where(skills.c.id == bindparam("skill_id")).values(**update_payload)
    conn.execute(stmt, {"skill_id": skill_id})


def upgrade() -> None:
    conn = op.get_bind()
    package_id = _find_package(conn)
    if package_id is None:
        package_id = _create_package(conn)

    _sync_package(conn, package_id)
    _soft_delete_legacy_skills(conn)
    for skill_payload in UI_RUNTIME_SKILLS:
        _upsert_skill(conn, package_id, skill_payload)


def downgrade() -> None:
    print("[SEED] Downgrade: no-op for UI Runtime page tools seed.")
