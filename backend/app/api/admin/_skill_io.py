"""
Skill 导入/导出辅助模块 / Skill Import/Export Helper Module

导出：将 Skill 转为 JSON，自动脱敏 config 中含 _env 后缀的字段
Export: Convert Skill to JSON, auto-sanitize config fields with _env suffix
导入：从 JSON 批量创建 Skill，支持冲突解决（skip/overwrite/rename）
Import: Batch create Skill from JSON, supports conflict resolution (skip/overwrite/rename)
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.models.ai.skill import Skill

# 导出字段白名单 / Export field whitelist
_EXPORT_FIELDS = [
    "name", "description", "avatar", "type", "config",
    "input_schema", "output_schema", "timeout", "is_active",
    "toolkit_content",
]

# 敏感 key 模式：含 secret/password/token/key/_env 后缀 / Sensitive key pattern: containing secret/password/token/key/_env suffix
_SENSITIVE_RE = re.compile(
    r"(secret|password|token|api_key|_env)$", re.IGNORECASE,
)


def _sanitize_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    """脱敏 config 中的敏感字段：保留 key 名但清空值 / Sanitize sensitive fields in config: keep key names but clear values"""
    if not config:
        return config
    sanitized = {}
    for k, v in config.items():
        if _SENSITIVE_RE.search(k):
            sanitized[k] = ""
        elif isinstance(v, dict):
            sanitized[k] = _sanitize_config(v)
        elif isinstance(v, list):
            sanitized[k] = [
                _sanitize_config(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


def export_skills(skills: list[Skill]) -> list[dict[str, Any]]:
    """
    将 Skill 列表导出为 JSON 可序列化的字典列表
    Export Skill list as JSON-serializable dict list

    Args:
        skills: Skill ORM 对象列表 / Skill ORM object list

    Returns:
        脱敏后的字典列表 / Sanitized dict list
    """
    result = []
    for skill in skills:
        item: dict[str, Any] = {}
        for field in _EXPORT_FIELDS:
            val = getattr(skill, field, None)
            item[field] = val
        # 脱敏 config / Sanitize config
        item["config"] = _sanitize_config(item.get("config"))
        result.append(item)
    return result


async def import_skills(
    db: AsyncSession,
    items: list[dict[str, Any]],
    tenant_id: int | None,
    conflict_mode: str = "skip",
    package_id: int | None = None,
) -> dict[str, Any]:
    """
    从 JSON 列表批量导入 Skill / Batch import Skill from JSON list

    Args:
        db: 数据库会话 / Database session
        items: 技能配置列表 / Skill config list
        tenant_id: 租户 ID（用于查询已有同名技能） / Tenant ID (for querying existing same-name skills)
        conflict_mode: 冲突解决方式 skip/overwrite/rename / Conflict resolution mode
        package_id: 导入到指定技能包（必填） / Import to specified skill package (required)

    Returns:
        {"created": int, "updated": int, "skipped": int, "errors": list[str]}
    """
    _VALID_MODES = {"skip", "overwrite", "rename"}
    if conflict_mode not in _VALID_MODES:
        conflict_mode = "skip"

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    # 查询现有同名 Skill / Query existing same-name skills
    existing_names: dict[str, Skill] = {}
    stmt = sa_select(Skill).where(
        Skill.is_deleted == False,  # noqa: E712
    )
    if tenant_id is not None:
        stmt = stmt.where(Skill.tenant_id == tenant_id)
    else:
        stmt = stmt.where(Skill.tenant_id.is_(None))
    result = await db.execute(stmt)
    for skill in result.scalars().all():
        existing_names[skill.name] = skill

    for idx, item in enumerate(items):
        name = item.get("name", "").strip()
        if not name:
            errors.append(_("skill.import.error.no_name", index=idx + 1))
            continue

        skill_type = item.get("type", "")
        if not skill_type:
            errors.append(_("skill.import.error.no_type", index=idx + 1, name=name))
            continue

        try:
            if name in existing_names:
                if conflict_mode == "skip":
                    skipped += 1
                    continue
                elif conflict_mode == "overwrite":
                    # 更新现有 Skill / Update existing Skill
                    existing = existing_names[name]
                    for field in _EXPORT_FIELDS:
                        if field == "name":
                            continue
                        if field in item:
                            setattr(existing, field, item[field])
                    updated += 1
                elif conflict_mode == "rename":
                    # 自动重命名 / Auto-rename
                    suffix = 1
                    new_name = f"{name} ({suffix})"
                    while new_name in existing_names:
                        suffix += 1
                        new_name = f"{name} ({suffix})"
                    item["name"] = new_name
                    name = new_name
                    # 创建新的 / Create new
                    create_data = {k: item[k] for k in _EXPORT_FIELDS if k in item}
                    if package_id is not None:
                        create_data["package_id"] = package_id
                    skill = Skill(
                        tenant_id=tenant_id,
                        **create_data,
                    )
                    db.add(skill)
                    existing_names[name] = skill
                    created += 1
                else:
                    skipped += 1
                    continue
            else:
                # 创建新 Skill / Create new Skill
                create_data = {k: item[k] for k in _EXPORT_FIELDS if k in item}
                if package_id is not None:
                    create_data["package_id"] = package_id
                skill = Skill(
                    tenant_id=tenant_id,
                    **create_data,
                )
                db.add(skill)
                existing_names[name] = skill
                created += 1
        except Exception as exc:
            errors.append(f"{name}: {str(exc)}")

    await db.flush()

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }


__all__ = ["export_skills", "import_skills"]
