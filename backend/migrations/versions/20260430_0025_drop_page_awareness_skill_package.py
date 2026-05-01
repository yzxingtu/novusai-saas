"""drop page awareness skill package

Revision ID: 20260430_0025_drop_page_skill
Revises: 20260430_0024_retire_page_skill
Create Date: 2026-04-30

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import MetaData, Table, bindparam, func, inspect, or_, select

revision: str = "20260430_0025_drop_page_skill"
down_revision: str | Sequence[str] | None = "20260430_0024_retire_page_skill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PAGE_AWARENESS_PACKAGE_NAME = "页面感知交互"
PAGE_AWARENESS_PACKAGE_TOOL_NAMES = (
    "append_content",
    "editor_ops",
    "get_editor_html",
    "get_editor_text",
    "ui_get_snapshot",
    "ui_read_region",
    "ui_read_table",
    "ui_list_interactables",
    "ui_click",
    "ui_open_surface",
    "ui_get_form_state",
    "ui_set_field",
    "ui_fill_form",
    "ui_submit_form",
    "get_page_context",
    "insert_content",
    "invoke_page_operation",
    "list_page_operations",
    "page_ops",
    "replace_content",
    "replace_section",
)
PAGE_AWARENESS_GLOBAL_TOOL_NAMES = (
    "ui_get_snapshot",
    "ui_read_region",
    "ui_read_table",
    "ui_list_interactables",
    "ui_click",
    "ui_open_surface",
    "ui_get_form_state",
    "ui_set_field",
    "ui_fill_form",
    "ui_submit_form",
    "get_page_context",
    "invoke_page_operation",
    "list_page_operations",
    "page_ops",
)
PAGE_AWARENESS_GLOBAL_TOOL_PREFIXES = ("pageop_",)
ROUTER_AGENT_NAME = "系统路由智能体"
ROUTER_SYSTEM_PROMPT = """\
You are an intelligent routing agent. Analyze the user's message and select the \
most appropriate agent from the available candidates.

Rules:
1. Analyze the user's intent from the message content.
2. Match the intent against each candidate agent's name and description.
3. Ignore current-page, DOM, screenshot, page-session, and editor-instance state; \
those signals are not part of AI dialogue routing.
4. Return your decision as a JSON object with exactly two fields:
   - agent_id: the integer ID of the selected agent
   - confidence: a float between 0.0 and 1.0 indicating your confidence

Response format (ONLY output this JSON, nothing else):
{"agent_id": <id>, "confidence": <0.0-1.0>}

If none of the candidates clearly match, select the most general-purpose one \
and set confidence below 0.5.\
"""
NOVUSDOC_AGENT_NAME = "NovusDoc Writer"
NOVUSDOC_SYSTEM_PROMPT = (
    "You are NovusDoc Writer, an AI writing assistant for explicit writing tasks. "
    "You help users continue, optimize, proofread, translate, summarize, expand, "
    "and rewrite content that the user provides directly or through an authorized "
    "backend document/read-model tool. Match the document's style, tone, and "
    "language. Be concise and accurate.\n\n"
    "Do not infer content from the current page, DOM, screenshots, page sessions, "
    "or editor runtime state. If more document content is needed, ask the user to "
    "provide it or use an explicit backend/API or permissioned skill-pack tool. "
    "Do not echo HTML, JSON or raw tool output to the user; respond in natural "
    "language only."
)


def _table_columns(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return set()
    return {
        str(column["name"])
        for column in inspector.get_columns(table_name)
        if column.get("name")
    }


def _reflect_table(conn, table_name: str) -> Table | None:
    if not _table_columns(conn, table_name):
        return None
    return Table(table_name, MetaData(), autoload_with=conn)


def _fetch_ids(conn, stmt, params: dict[str, object]) -> list[int]:
    return [int(row[0]) for row in conn.execute(stmt, params).fetchall()]


def _page_package_ids(conn) -> list[int]:
    columns = _table_columns(conn, "skill_packages")
    if not {"id", "name"}.issubset(columns):
        return []
    skill_packages = _reflect_table(conn, "skill_packages")
    if skill_packages is None:
        return []
    return _fetch_ids(
        conn,
        select(skill_packages.c.id)
        .where(skill_packages.c.name == bindparam("package_name"))
        .order_by(skill_packages.c.id),
        {"package_name": PAGE_AWARENESS_PACKAGE_NAME},
    )


def _page_skill_ids(conn, package_ids: list[int]) -> list[int]:
    columns = _table_columns(conn, "skills")
    if not {"id", "name"}.issubset(columns):
        return []
    skills = _reflect_table(conn, "skills")
    if skills is None:
        return []

    predicates = [skills.c.name.in_(bindparam("global_tool_names", expanding=True))]
    params: dict[str, object] = {
        "global_tool_names": list(PAGE_AWARENESS_GLOBAL_TOOL_NAMES),
    }
    for idx, prefix in enumerate(PAGE_AWARENESS_GLOBAL_TOOL_PREFIXES):
        param_name = f"tool_prefix_{idx}"
        predicates.append(skills.c.name.like(bindparam(param_name)))
        params[param_name] = f"{prefix}%"
    if package_ids and "package_id" in columns:
        predicates.append(
            skills.c.package_id.in_(bindparam("package_ids", expanding=True))
        )
        params["package_ids"] = package_ids

    return _fetch_ids(
        conn,
        select(skills.c.id).where(or_(*predicates)).order_by(skills.c.id),
        params,
    )


def _capability_ids_for_skills(conn, skill_ids: list[int]) -> list[int]:
    if not skill_ids:
        return []
    columns = _table_columns(conn, "skill_capability_bindings")
    if not {"skill_id", "capability_id"}.issubset(columns):
        return []
    bindings = _reflect_table(conn, "skill_capability_bindings")
    if bindings is None:
        return []
    return _fetch_ids(
        conn,
        select(bindings.c.capability_id)
        .where(bindings.c.skill_id.in_(bindparam("skill_ids", expanding=True)))
        .order_by(bindings.c.capability_id),
        {"skill_ids": skill_ids},
    )


def _page_capability_ids(conn, skill_ids: list[int]) -> list[int]:
    columns = _table_columns(conn, "capabilities")
    if "id" not in columns:
        return _capability_ids_for_skills(conn, skill_ids)
    capabilities = _reflect_table(conn, "capabilities")
    if capabilities is None:
        return _capability_ids_for_skills(conn, skill_ids)

    capability_ids = _capability_ids_for_skills(conn, skill_ids)
    predicates = []
    params: dict[str, object] = {
        "tool_names": list(PAGE_AWARENESS_GLOBAL_TOOL_NAMES),
    }
    if "key" in columns:
        predicates.append(capabilities.c.key.in_(bindparam("tool_names", expanding=True)))
        for idx, prefix in enumerate(PAGE_AWARENESS_GLOBAL_TOOL_PREFIXES):
            param_name = f"tool_key_prefix_{idx}"
            predicates.append(capabilities.c.key.like(bindparam(param_name)))
            params[param_name] = f"{prefix}%"
    if "executor_ref" in columns:
        predicates.append(
            capabilities.c.executor_ref.in_(
                bindparam("executor_tool_names", expanding=True)
            )
        )
        params["executor_tool_names"] = list(PAGE_AWARENESS_GLOBAL_TOOL_NAMES)
        for idx, prefix in enumerate(PAGE_AWARENESS_GLOBAL_TOOL_PREFIXES):
            param_name = f"executor_tool_prefix_{idx}"
            predicates.append(capabilities.c.executor_ref.like(bindparam(param_name)))
            params[param_name] = f"{prefix}%"
    if not predicates:
        return sorted(set(capability_ids))
    capability_ids.extend(_fetch_ids(
        conn,
        select(capabilities.c.id).where(or_(*predicates)).order_by(capabilities.c.id),
        params,
    ))
    return sorted(set(capability_ids))


def _update_seeded_agent_prompt(
    conn,
    *,
    agent_name: str,
    system_prompt: str,
) -> None:
    columns = _table_columns(conn, "agents")
    if not {"name", "system_prompt"}.issubset(columns):
        return
    agents = _reflect_table(conn, "agents")
    if agents is None:
        return

    predicates = [agents.c.name == bindparam("agent_name")]
    if "tenant_id" in columns:
        predicates.append(agents.c.tenant_id.is_(None))
    if "is_deleted" in columns:
        predicates.append(agents.c.is_deleted.is_(False))

    values: dict[str, object] = {"system_prompt": system_prompt}
    if "updated_at" in columns:
        values["updated_at"] = func.now()

    conn.execute(
        agents.update().where(*predicates).values(**values),
        {"agent_name": agent_name},
    )


def _retire_seeded_page_prompt_text(conn) -> None:
    _update_seeded_agent_prompt(
        conn,
        agent_name=ROUTER_AGENT_NAME,
        system_prompt=ROUTER_SYSTEM_PROMPT,
    )
    _update_seeded_agent_prompt(
        conn,
        agent_name=NOVUSDOC_AGENT_NAME,
        system_prompt=NOVUSDOC_SYSTEM_PROMPT,
    )


def _delete_by_ids(conn, table_name: str, column_name: str, ids: list[int]) -> None:
    if not ids:
        return
    columns = _table_columns(conn, table_name)
    if column_name not in columns:
        return
    table = _reflect_table(conn, table_name)
    if table is None:
        return
    stmt = table.delete().where(
        table.c[column_name].in_(bindparam("target_ids", expanding=True))
    )
    conn.execute(stmt, {"target_ids": ids})


def _delete_legacy_agent_skill_bindings(
    conn,
    *,
    package_ids: list[int],
    skill_ids: list[int],
) -> None:
    columns = _table_columns(conn, "agent_skill_bindings")
    if not columns:
        return
    agent_skill_bindings = _reflect_table(conn, "agent_skill_bindings")
    if agent_skill_bindings is None:
        return

    predicates = []
    params: dict[str, object] = {}
    if skill_ids and "skill_id" in columns:
        predicates.append(
            agent_skill_bindings.c.skill_id.in_(
                bindparam("binding_skill_ids", expanding=True)
            )
        )
        params["binding_skill_ids"] = skill_ids
    if package_ids and "package_id" in columns:
        predicates.append(
            agent_skill_bindings.c.package_id.in_(
                bindparam("binding_package_ids", expanding=True)
            )
        )
        params["binding_package_ids"] = package_ids
    if not predicates:
        return

    conn.execute(agent_skill_bindings.delete().where(or_(*predicates)), params)


def upgrade() -> None:
    conn = op.get_bind()
    package_ids = _page_package_ids(conn)
    skill_ids = _page_skill_ids(conn, package_ids)
    capability_ids = _page_capability_ids(conn, skill_ids)

    _delete_by_ids(conn, "agent_skill_grants", "skill_id", skill_ids)
    _delete_legacy_agent_skill_bindings(
        conn,
        package_ids=package_ids,
        skill_ids=skill_ids,
    )
    _delete_by_ids(conn, "skill_resources", "skill_id", skill_ids)
    _delete_by_ids(conn, "skill_capability_bindings", "skill_id", skill_ids)
    _delete_by_ids(
        conn,
        "skill_capability_bindings",
        "capability_id",
        capability_ids,
    )
    _delete_by_ids(conn, "capabilities", "id", capability_ids)
    _delete_by_ids(conn, "skills", "id", skill_ids)
    _delete_by_ids(conn, "skill_packages", "id", package_ids)
    _retire_seeded_page_prompt_text(conn)


def downgrade() -> None:
    # New-system boundary: page awareness must not be restored by downgrade.
    # 新系统边界：页面感知不再通过 downgrade 恢复。
    pass
