"""中文: 播种 system.ai_writing 富文本契约并隐藏旧 NovusDoc catalog 项。

EN: Seed the system.ai_writing rich-text contract and hide legacy NovusDoc catalog items.

Revision ID: 20260505_0027_novusdoc_richai
Revises: 20260502_0026_admin_ai_enabled
Create Date: 2026-05-05

"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260505_0027_novusdoc_richai"
down_revision: str | Sequence[str] | None = "20260502_0026_admin_ai_enabled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLUGIN_NAME = "novusdoc"
MANIFEST_FEATURE_CODE = "rich_text_ai"
INTERNAL_COMPAT_FEATURE_CODE = "plugin.novusdoc.rich_text_ai"
FEATURE_CODE = "system.ai_writing"
FEATURE_NAME = "AI Writing Assistant"
FEATURE_DESCRIPTION = (
    "Platform-level AI writing assignment used by NovusDoc and other rich-text "
    "editors. Supports continue, rewrite, insert, formatting, translate, "
    "proofread, summarize, expand, custom instruction, and chat actions."
)
RICH_TEXT_PACKAGE_NAME = "NovusDoc Rich Text AI"
RICH_TEXT_SKILL_KEY = "novusdoc.rich_text_ai.actions"
HIDE_MARKER_KEY = "hidden_by_20260505_0027"
HIDE_MARKER_PATH = "{hidden_by_20260505_0027}"

AI_REQUIREMENTS = {
    "features": [],
    "required_model_types": ["chat"],
    "min_context_window": 4096,
}

_ACTIONS = [
    {
        "code": "continue",
        "label": {"zh-CN": "续写", "en": "Continue"},
        "backend_feature": "continue",
        "operation": "insert_after_cursor",
        "requires_selection": False,
        "preserve_formatting": True,
    },
    {
        "code": "rewrite",
        "label": {"zh-CN": "改写", "en": "Rewrite"},
        "backend_feature": "rewrite",
        "operation": "replace_selection",
        "requires_selection": True,
        "preserve_formatting": True,
    },
    {
        "code": "insert",
        "label": {"zh-CN": "新增", "en": "Insert"},
        "backend_feature": "custom",
        "operation": "insert_at_cursor",
        "requires_selection": False,
        "instruction_required": True,
        "preserve_formatting": True,
    },
    {
        "code": "format",
        "label": {"zh-CN": "增加格式", "en": "Format"},
        "backend_feature": "custom",
        "operation": "replace_selection",
        "requires_selection": True,
        "format_instruction_supported": True,
        "preserve_formatting": True,
    },
    {
        "code": "optimize",
        "label": {"zh-CN": "优化", "en": "Optimize"},
        "backend_feature": "optimize",
        "operation": "replace_selection",
        "requires_selection": True,
        "preserve_formatting": True,
    },
    {
        "code": "proofread",
        "label": {"zh-CN": "校对", "en": "Proofread"},
        "backend_feature": "proofread",
        "operation": "replace_selection",
        "requires_selection": True,
        "preserve_formatting": True,
    },
    {
        "code": "translate",
        "label": {"zh-CN": "翻译", "en": "Translate"},
        "backend_feature": "translate",
        "operation": "replace_selection",
        "requires_selection": True,
        "target_lang_supported": True,
        "preserve_formatting": True,
    },
    {
        "code": "summarize",
        "label": {"zh-CN": "摘要", "en": "Summarize"},
        "backend_feature": "summarize",
        "operation": "replace_selection",
        "requires_selection": True,
        "preserve_formatting": False,
    },
    {
        "code": "expand",
        "label": {"zh-CN": "扩写", "en": "Expand"},
        "backend_feature": "expand",
        "operation": "replace_selection",
        "requires_selection": True,
        "preserve_formatting": True,
    },
    {
        "code": "custom",
        "label": {"zh-CN": "自定义", "en": "Custom"},
        "backend_feature": "custom",
        "operation": "replace_or_insert",
        "requires_selection": False,
        "instruction_required": True,
        "preserve_formatting": True,
    },
    {
        "code": "chat",
        "label": {"zh-CN": "对话", "en": "Chat"},
        "backend_feature": "chat",
        "operation": "assistant_reply",
        "requires_selection": False,
        "side_panel": True,
        "preserve_formatting": False,
    },
]


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_column(bind, table_name: str, column_name: str) -> bool:
    if not _has_table(bind, table_name):
        return False
    inspector = sa.inspect(bind)
    return any(
        column.get("name") == column_name
        for column in inspector.get_columns(table_name)
    )


def _has_columns(bind, table_name: str, column_names: tuple[str, ...]) -> bool:
    return all(_has_column(bind, table_name, name) for name in column_names)


def default_action_config(feature_code: str = FEATURE_CODE) -> dict[str, Any]:
    """中文: 返回 system.ai_writing 的富文本动作数据契约。

    EN: Return the rich-text action data contract for system.ai_writing.
    """
    return {
        "schema_version": 1,
        "feature_code": feature_code,
        "scene": "novusdoc.rich_text_editor",
        "editor": "novusdoc",
        "endpoint_kind": "ai_writing_sse",
        "default_action": "custom",
        "input_contract": {
            "selected_text": {"max_length": 5000, "required": False},
            "before_text": {"max_length": 2000, "required": False},
            "after_text": {"max_length": 500, "required": False},
            "instruction": {"max_length": 1000, "required": False},
            "context_title": {"max_length": 200, "required": False},
            "target_lang": {"max_length": 50, "required": False},
        },
        "security": {
            "page_context_allowed": False,
            "dom_runtime_allowed": False,
            "allowed_data_source": "explicit_editor_payload",
        },
        "actions": list(_ACTIONS),
    }


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _resolve_default_agent_id(bind) -> int | None:
    assignment_row = bind.execute(
        text("""
            SELECT agent_id
            FROM system_agent_assignments
            WHERE feature_code = :feature_code
              AND tenant_id IS NULL
              AND agent_id IS NOT NULL
              AND is_deleted = false
            ORDER BY id
            LIMIT 1
            """),
        {"feature_code": FEATURE_CODE},
    ).fetchone()
    if assignment_row is not None:
        return int(assignment_row[0])
    if not _has_column(bind, "agents", "source_plugin"):
        return None
    agent_row = bind.execute(
        text("""
            SELECT id
            FROM agents
            WHERE source_plugin = :plugin_name
              AND owner_tenant_id IS NULL
              AND status = 'published'
              AND is_deleted = false
            ORDER BY id
            LIMIT 1
            """),
        {"plugin_name": PLUGIN_NAME},
    ).fetchone()
    return int(agent_row[0]) if agent_row is not None else None


def _ensure_assignment(
    bind,
    *,
    feature_code: str,
    feature_name: str,
    description: str,
    agent_id: int | None,
) -> None:
    if not _has_table(bind, "system_agent_assignments"):
        return
    config_json = _json_dumps(default_action_config(feature_code))
    existing = bind.execute(
        text("""
            SELECT id
            FROM system_agent_assignments
            WHERE feature_code = :feature_code
              AND tenant_id IS NULL
              AND is_deleted = false
            ORDER BY id
            LIMIT 1
            """),
        {"feature_code": feature_code},
    ).fetchone()
    if existing is None:
        bind.execute(
            text("""
                INSERT INTO system_agent_assignments (
                    feature_code, feature_name, description, tenant_id, agent_id,
                    config, is_active, created_at, updated_at, is_deleted
                )
                VALUES (
                    :feature_code, :feature_name, :description, NULL, :agent_id,
                    CAST(:config_json AS JSON), true, NOW(), NOW(), false
                )
                """),
            {
                "feature_code": feature_code,
                "feature_name": feature_name,
                "description": description,
                "agent_id": agent_id,
                "config_json": config_json,
            },
        )
        return
    bind.execute(
        text("""
            UPDATE system_agent_assignments
            SET config = CAST(:config_json AS JSON), updated_at = NOW()
            WHERE id = :assignment_id AND config IS NULL
            """),
        {"assignment_id": int(existing[0]), "config_json": config_json},
    )


def _cleanup_system_assignment_config(bind) -> None:
    if not _has_table(bind, "system_agent_assignments"):
        return
    bind.execute(
        text("""
            UPDATE system_agent_assignments
            SET config = (
                    config::jsonb
                    - 'catalog_feature_code'
                    - 'runtime_feature_code'
                    - 'legacy_runtime_feature_code'
                    - 'fallback_policy'
                )::json,
                updated_at = NOW()
            WHERE feature_code = :feature_code
              AND tenant_id IS NULL
              AND is_deleted = false
              AND config IS NOT NULL
              AND (
                  config::jsonb ? 'catalog_feature_code'
                  OR config::jsonb ? 'runtime_feature_code'
                  OR config::jsonb ? 'legacy_runtime_feature_code'
                  OR config::jsonb ? 'fallback_policy'
              )
            """),
        {"feature_code": FEATURE_CODE},
    )


def _delete_unbound_legacy_plugin_assignment(bind) -> None:
    """中文: 仅移除插件生命周期误建的空 legacy runtime 行。

    EN: Remove only the empty legacy runtime row created by plugin lifecycle.
    """
    if not _has_table(bind, "system_agent_assignments"):
        return
    bind.execute(
        text("""
            DELETE FROM system_agent_assignments
            WHERE feature_code = :internal_compat_feature_code
              AND tenant_id IS NULL
              AND agent_id IS NULL
              AND config IS NULL
              AND is_deleted = false
            """),
        {"internal_compat_feature_code": INTERNAL_COMPAT_FEATURE_CODE},
    )


def _hide_default_rich_text_skill_package(bind) -> None:
    """中文: 软隐藏旧系统富文本技能包，保留人工数据可恢复。

    EN: Soft-hide the legacy system rich-text package while preserving manual data.
    """
    if not _has_table(bind, "skill_packages"):
        return
    package_columns = (
        "id",
        "name",
        "tenant_id",
        "is_system",
        "is_active",
        "is_recommended",
        "is_deleted",
        "deleted_at",
        "delete_level",
        "recycle_stage",
        "updated_at",
        "valves_config",
    )
    if not _has_columns(bind, "skill_packages", package_columns):
        return
    has_skill_lookup = _has_table(bind, "skills") and _has_columns(
        bind,
        "skills",
        (
            "package_id",
            "key",
            "source_ref",
            "is_system",
            "is_active",
            "is_deleted",
            "deleted_at",
            "delete_level",
            "recycle_stage",
            "updated_at",
            "status",
            "config",
        ),
    )
    if has_skill_lookup:
        bind.execute(
            text("""
                WITH target_packages AS (
                    SELECT pkg.id
                    FROM skill_packages AS pkg
                    WHERE pkg.tenant_id IS NULL
                      AND pkg.is_system = true
                      AND pkg.is_deleted = false
                      AND (pkg.is_active = true OR pkg.is_recommended = true)
                      AND (
                          pkg.name = :package_name
                          OR EXISTS (
                              SELECT 1
                              FROM skills AS skill
                              WHERE skill.package_id = pkg.id
                                AND skill.is_system = true
                                AND skill.is_deleted = false
                                AND (
                                    skill.key = :skill_key
                                    OR skill.source_ref = :skill_key
                                )
                          )
                      )
                )
                UPDATE skills AS skill
                SET is_active = false,
                    status = 'disabled',
                    config = jsonb_set(
                        COALESCE(skill.config::jsonb, '{}'::jsonb),
                        CAST(:hide_marker_path AS text[]),
                        'true'::jsonb,
                        true
                    )::json,
                    is_deleted = true,
                    deleted_at = NOW(),
                    delete_level = 'admin',
                    recycle_stage = 'module',
                    updated_at = NOW()
                WHERE skill.package_id IN (SELECT id FROM target_packages)
                  AND skill.is_system = true
                  AND skill.is_deleted = false
                  AND (skill.is_active = true OR skill.status = 'active')
                  AND (skill.key = :skill_key OR skill.source_ref = :skill_key)
                """),
            {
                "package_name": RICH_TEXT_PACKAGE_NAME,
                "skill_key": RICH_TEXT_SKILL_KEY,
                "hide_marker_path": HIDE_MARKER_PATH,
            },
        )
        bind.execute(
            text("""
                WITH target_packages AS (
                    SELECT pkg.id
                    FROM skill_packages AS pkg
                    WHERE pkg.tenant_id IS NULL
                      AND pkg.is_system = true
                      AND pkg.is_deleted = false
                      AND (pkg.is_active = true OR pkg.is_recommended = true)
                      AND (
                          pkg.name = :package_name
                          OR EXISTS (
                              SELECT 1
                              FROM skills AS skill
                              WHERE skill.package_id = pkg.id
                                AND (
                                    skill.key = :skill_key
                                    OR skill.source_ref = :skill_key
                                )
                          )
                      )
                )
                UPDATE skill_packages AS pkg
                SET is_active = false,
                    is_recommended = false,
                    valves_config = jsonb_set(
                        COALESCE(pkg.valves_config::jsonb, '{}'::jsonb),
                        CAST(:hide_marker_path AS text[]),
                        'true'::jsonb,
                        true
                    ),
                    is_deleted = true,
                    deleted_at = NOW(),
                    delete_level = 'admin',
                    recycle_stage = 'module',
                    updated_at = NOW()
                WHERE pkg.id IN (SELECT id FROM target_packages)
                """),
            {
                "package_name": RICH_TEXT_PACKAGE_NAME,
                "skill_key": RICH_TEXT_SKILL_KEY,
                "hide_marker_path": HIDE_MARKER_PATH,
            },
        )
        return
    bind.execute(
        text("""
            UPDATE skill_packages
            SET is_active = false,
                is_recommended = false,
                valves_config = jsonb_set(
                    COALESCE(valves_config::jsonb, '{}'::jsonb),
                    CAST(:hide_marker_path AS text[]),
                    'true'::jsonb,
                    true
                ),
                is_deleted = true,
                deleted_at = NOW(),
                delete_level = 'admin',
                recycle_stage = 'module',
                updated_at = NOW()
            WHERE tenant_id IS NULL
              AND is_system = true
              AND is_deleted = false
              AND (is_active = true OR is_recommended = true)
              AND name = :package_name
            """),
        {"package_name": RICH_TEXT_PACKAGE_NAME, "hide_marker_path": HIDE_MARKER_PATH},
    )


def _sync_plugin_metadata(bind) -> None:
    if not _has_table(bind, "plugins"):
        return
    ai_requirements_json = _json_dumps(AI_REQUIREMENTS)
    bind.execute(
        text("""
            WITH base AS (
                SELECT id,
                    CASE
                        WHEN ai_requirements IS NULL
                            THEN CAST(:ai_requirements_json AS JSONB)
                        ELSE jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    ai_requirements::jsonb,
                                    '{features}',
                                    '[]'::jsonb,
                                    true
                                ),
                                '{required_model_types}',
                                jsonb_build_array('chat'),
                                true
                            ),
                            '{min_context_window}',
                            to_jsonb(4096),
                            true
                        )
                    END AS next_ai_requirements,
                    COALESCE(manifest::jsonb, '{}'::jsonb) AS current_manifest
                FROM plugins
                WHERE name = :plugin_name AND is_deleted = false
            ),
            target AS (
                SELECT id,
                    next_ai_requirements,
                    CASE
                        WHEN jsonb_typeof(current_manifest -> 'features') = 'array'
                            THEN jsonb_set(
                                current_manifest,
                                '{features}',
                                COALESCE(
                                    (
                                        SELECT jsonb_agg(feature)
                                        FROM jsonb_array_elements(
                                            current_manifest -> 'features'
                                        ) AS feature
                                        WHERE feature ->> 'code'
                                            <> :manifest_feature_code
                                    ),
                                    '[]'::jsonb
                                ),
                                true
                            )
                        ELSE jsonb_set(
                            current_manifest,
                            '{features}',
                            '[]'::jsonb,
                            true
                        )
                    END AS next_manifest_base
                FROM base
            )
            UPDATE plugins AS plugin
            SET ai_requirements = target.next_ai_requirements::json,
                manifest = jsonb_set(
                    target.next_manifest_base,
                    '{ai_requirements}',
                    target.next_ai_requirements,
                    true
                )::json,
                updated_at = NOW()
            FROM target
            WHERE plugin.id = target.id
            """),
        {
            "plugin_name": PLUGIN_NAME,
            "manifest_feature_code": MANIFEST_FEATURE_CODE,
            "ai_requirements_json": ai_requirements_json,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "system_agent_assignments"):
        return
    default_agent_id = _resolve_default_agent_id(bind)
    _ensure_assignment(
        bind,
        feature_code=FEATURE_CODE,
        feature_name=FEATURE_NAME,
        description=FEATURE_DESCRIPTION,
        agent_id=default_agent_id,
    )
    _cleanup_system_assignment_config(bind)
    _delete_unbound_legacy_plugin_assignment(bind)
    _hide_default_rich_text_skill_package(bind)
    _sync_plugin_metadata(bind)


def _restore_hidden_default_rich_text_skill_package(bind) -> None:
    if not _has_table(bind, "skill_packages"):
        return
    if not _has_columns(
        bind,
        "skill_packages",
        (
            "tenant_id",
            "is_system",
            "is_active",
            "is_recommended",
            "is_deleted",
            "deleted_at",
            "delete_level",
            "recycle_stage",
            "updated_at",
            "valves_config",
        ),
    ):
        return
    if _has_table(bind, "skills") and _has_columns(
        bind,
        "skills",
        (
            "package_id",
            "key",
            "source_ref",
            "is_system",
            "is_active",
            "is_deleted",
            "deleted_at",
            "delete_level",
            "recycle_stage",
            "updated_at",
            "status",
            "config",
        ),
    ):
        bind.execute(
            text("""
                WITH target_packages AS (
                    SELECT id
                    FROM skill_packages
                    WHERE tenant_id IS NULL
                      AND is_system = true
                      AND is_deleted = true
                      AND COALESCE(valves_config::jsonb, '{}'::jsonb)
                          ->> :hide_marker_key = 'true'
                )
                UPDATE skills AS skill
                SET is_active = true,
                    status = 'active',
                    config = (COALESCE(skill.config::jsonb, '{}'::jsonb)
                        - :hide_marker_key)::json,
                    is_deleted = false,
                    deleted_at = NULL,
                    delete_level = NULL,
                    recycle_stage = NULL,
                    updated_at = NOW()
                WHERE skill.package_id IN (SELECT id FROM target_packages)
                  AND skill.is_system = true
                  AND skill.is_deleted = true
                  AND COALESCE(skill.config::jsonb, '{}'::jsonb)
                      ->> :hide_marker_key = 'true'
                  AND (skill.key = :skill_key OR skill.source_ref = :skill_key)
                """),
            {"hide_marker_key": HIDE_MARKER_KEY, "skill_key": RICH_TEXT_SKILL_KEY},
        )
    bind.execute(
        text("""
            UPDATE skill_packages AS pkg
            SET is_active = true,
                is_recommended = true,
                valves_config = COALESCE(pkg.valves_config::jsonb, '{}'::jsonb)
                    - :hide_marker_key,
                is_deleted = false,
                deleted_at = NULL,
                delete_level = NULL,
                recycle_stage = NULL,
                updated_at = NOW()
            WHERE pkg.tenant_id IS NULL
              AND pkg.is_system = true
              AND pkg.is_deleted = true
              AND COALESCE(pkg.valves_config::jsonb, '{}'::jsonb)
                  ->> :hide_marker_key = 'true'
              AND pkg.name = :package_name
            """),
        {"hide_marker_key": HIDE_MARKER_KEY, "package_name": RICH_TEXT_PACKAGE_NAME},
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "system_agent_assignments"):
        return
    _restore_hidden_default_rich_text_skill_package(bind)
    config_json = _json_dumps(default_action_config(FEATURE_CODE))
    bind.execute(
        text("""
            UPDATE system_agent_assignments
            SET config = NULL, updated_at = NOW()
            WHERE feature_code = :feature_code
              AND tenant_id IS NULL
              AND config::jsonb = CAST(:config_json AS JSONB)
            """),
        {"feature_code": FEATURE_CODE, "config_json": config_json},
    )
