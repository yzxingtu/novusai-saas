"""
技能包导入/导出工具

导出格式 (v1):
{
    "export_version": 1,
    "package_info": { name, description, avatar, scope, ... },
    "skills": [ { name, type, description, config, toolkit_content, ... }, ... ],
    "valves_schema": { ... } | null,
}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage

logger = LogManager.get_logger("ai")

EXPORT_VERSION = 1

# 导出时技能字段白名单（排除运行时/ID/时间戳等）
_SKILL_EXPORT_FIELDS = [
    "name",
    "description",
    "avatar",
    "type",
    "config",
    "toolkit_content",
    "toolkit_meta",
    "input_schema",
    "output_schema",
    "is_system",
    "is_active",
    "sort_order",
    "timeout",
]

# 导出时技能包字段白名单
_PACKAGE_EXPORT_FIELDS = [
    "name",
    "description",
    "avatar",
    "scope",
    "is_system",
    "is_active",
    "sort_order",
    "source_plugin",
]


async def export_skill_package(
    db: AsyncSession,
    pkg: SkillPackage,
) -> dict[str, Any]:
    """
    导出技能包为 JSON 格式

    Args:
        db: 数据库会话
        pkg: 技能包模型实例

    Returns:
        导出数据字典
    """
    # 查询包内所有技能
    result = await db.execute(
        select(Skill).where(
            Skill.package_id == pkg.id,
            Skill.is_deleted.is_(False),
        ).order_by(Skill.sort_order),
    )
    skills = result.scalars().all()

    # 构建技能包信息
    package_info: dict[str, Any] = {}
    for field in _PACKAGE_EXPORT_FIELDS:
        package_info[field] = getattr(pkg, field, None)

    # 构建技能列表
    skills_data: list[dict[str, Any]] = []
    for skill in skills:
        skill_data: dict[str, Any] = {}
        for field in _SKILL_EXPORT_FIELDS:
            skill_data[field] = getattr(skill, field, None)
        skills_data.append(skill_data)

    return {
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "package_info": package_info,
        "skills": skills_data,
        "valves_schema": pkg.valves_schema,
    }


async def import_skill_package(
    db: AsyncSession,
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    从导出 JSON 导入技能包

    Args:
        db: 数据库会话
        data: 导入数据（包含 export_data + 导入选项）

    Returns:
        导入结果摘要
    """
    # 提取导入选项
    export_data = data.get("export_data", data)
    conflict_mode = data.get("conflict_mode", "rename")  # skip / rename
    target_scope = data.get("target_scope", "admin")
    target_tenant_id = data.get("target_tenant_id")

    # 校验格式
    version = export_data.get("export_version")
    if version != EXPORT_VERSION:
        raise BusinessException(
            message=_("skill_package.error.invalid_export_format"),
        )

    package_info = export_data.get("package_info")
    skills_data = export_data.get("skills", [])

    if not isinstance(package_info, dict) or not package_info.get("name"):
        raise BusinessException(
            message=_("skill_package.error.invalid_export_format"),
        )

    pkg_name = package_info["name"]

    # 检查同名技能包（按 scope + tenant_id 隔离，避免跨租户干扰）
    name_conditions = [
        SkillPackage.name == pkg_name,
        SkillPackage.scope == target_scope,
        SkillPackage.is_deleted.is_(False),
    ]
    if target_scope == "tenant" and target_tenant_id is not None:
        name_conditions.append(SkillPackage.tenant_id == target_tenant_id)
    elif target_scope in ("admin", "global"):
        name_conditions.append(SkillPackage.tenant_id.is_(None))

    existing = await db.execute(
        select(SkillPackage).where(*name_conditions),
    )
    existing_pkg = existing.scalar_one_or_none()

    if existing_pkg:
        if conflict_mode == "skip":
            return {
                "status": "skipped",
                "message": f"Package '{pkg_name}' already exists",
                "package_id": existing_pkg.id,
                "skills_created": 0,
            }
        elif conflict_mode == "rename":
            # 自动追加时间戳后缀
            suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            pkg_name = f"{pkg_name}_{suffix}"
        else:
            raise BusinessException(
                message=_("skill_package.error.name_exists"),
            )

    # 创建技能包
    new_pkg = SkillPackage(
        name=pkg_name,
        description=package_info.get("description"),
        avatar=package_info.get("avatar"),
        scope=target_scope,
        tenant_id=target_tenant_id,
        is_system=False,  # 导入的不标记为系统
        is_active=package_info.get("is_active", True),
        sort_order=package_info.get("sort_order", 0),
        source_plugin=package_info.get("source_plugin"),
        valves_schema=export_data.get("valves_schema"),
    )
    db.add(new_pkg)
    await db.flush()  # 获取 new_pkg.id

    # 创建技能
    from app.enums.agent import SkillTypeEnum
    valid_skill_types = SkillTypeEnum.values()

    skills_created = 0
    for skill_data in skills_data:
        skill_type = skill_data.get("type", "toolkit")
        if skill_type not in valid_skill_types:
            logger.warning(
                "Skipping skill with invalid type '%s' during import of '%s'",
                skill_type, pkg_name,
            )
            continue

        new_skill = Skill(
            package_id=new_pkg.id,
            tenant_id=target_tenant_id,
            name=skill_data.get("name", "Unnamed Skill"),
            description=skill_data.get("description"),
            avatar=skill_data.get("avatar"),
            type=skill_type,
            config=skill_data.get("config"),
            toolkit_content=skill_data.get("toolkit_content"),
            toolkit_meta=skill_data.get("toolkit_meta"),
            input_schema=skill_data.get("input_schema"),
            output_schema=skill_data.get("output_schema"),
            is_system=False,
            is_active=skill_data.get("is_active", True),
            sort_order=skill_data.get("sort_order", 0),
            timeout=skill_data.get("timeout", 30),
        )
        db.add(new_skill)
        skills_created += 1

    logger.info(
        "Skill package imported: %s (id=%d) with %d skills",
        pkg_name, new_pkg.id, skills_created,
    )

    return {
        "status": "created",
        "package_id": new_pkg.id,
        "package_name": pkg_name,
        "skills_created": skills_created,
    }
