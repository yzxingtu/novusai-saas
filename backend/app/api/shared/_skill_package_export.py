"""
技能包导入/导出工具 / Skill Package Import/Export Utilities

导出格式 / Export format (v1):
{
    "export_version": 1,
    "package_info": { name, description, avatar, ... },
    "skills": [ { name, type, description, config, toolkit_content, ... }, ... ],
    "valves_schema": { ... } | null,
}
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException
from app.models.ai.skill import Skill
from app.models.ai.skill_package import SkillPackage

logger = LogManager.get_logger("ai")

EXPORT_VERSION = 1

# 导出时技能字段白名单（排除运行时/ID/时间戳等） / Skill export field whitelist (excludes runtime/ID/timestamp fields)
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

# 导出时技能包字段白名单 / Package export field whitelist
_PACKAGE_EXPORT_FIELDS = [
    "name",
    "description",
    "avatar",
    "is_recommended",
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
    导出技能包为 JSON 格式 / Export skill package to JSON format

    Args:
        db: 数据库会话 / Database session
        pkg: 技能包模型实例 / SkillPackage model instance

    Returns:
        导出数据字典 / Export data dictionary
    """
    # 查询包内所有技能 / Query all skills in package
    result = await db.execute(
        select(Skill)
        .where(
            Skill.package_id == pkg.id,
            Skill.is_deleted.is_(False),
        )
        .order_by(Skill.sort_order),
    )
    skills = result.scalars().all()

    # 构建技能包信息 / Build package info
    package_info: dict[str, Any] = {}
    for field in _PACKAGE_EXPORT_FIELDS:
        package_info[field] = getattr(pkg, field, None)

    # 构建技能列表 / Build skills list
    skills_data: list[dict[str, Any]] = []
    for skill in skills:
        skill_data: dict[str, Any] = {}
        for field in _SKILL_EXPORT_FIELDS:
            skill_data[field] = getattr(skill, field, None)
        skills_data.append(skill_data)

    return {
        "export_version": EXPORT_VERSION,
        "exported_at": utc_now().isoformat(),
        "package_info": package_info,
        "skills": skills_data,
        "valves_schema": pkg.valves_schema,
    }


async def import_skill_package(
    db: AsyncSession,
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    从导出 JSON 导入技能包 / Import skill package from exported JSON

    Args:
        db: 数据库会话 / Database session
        data: 导入数据（包含 export_data + 导入选项） / Import data (contains export_data + import options)

    Returns:
        导入结果摘要 / Import result summary
    """
    export_data = data.get("export_data", data)
    conflict_mode = data.get("conflict_mode", "rename")
    target_tenant_id = data.get("target_tenant_id")

    # 校验格式 / Validate format
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

    name_conditions = [
        SkillPackage.name == pkg_name,
        SkillPackage.is_deleted.is_(False),
    ]
    if target_tenant_id is not None:
        name_conditions.append(SkillPackage.tenant_id == target_tenant_id)
    else:
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
            # 自动追加时间戳后缀 / Auto-append timestamp suffix
            suffix = utc_now().strftime("%Y%m%d%H%M%S")
            pkg_name = f"{pkg_name}_{suffix}"
        else:
            raise BusinessException(
                message=_("skill_package.error.name_exists"),
            )

    # 创建技能包 / Create skill package
    new_pkg = SkillPackage(
        name=pkg_name,
        description=package_info.get("description"),
        avatar=package_info.get("avatar"),
        is_recommended=package_info.get("is_recommended", False),
        tenant_id=target_tenant_id,
        is_system=False,  # 导入的不标记为系统 / Imported packages are not marked as system
        is_active=package_info.get("is_active", True),
        sort_order=package_info.get("sort_order", 0),
        source_plugin=package_info.get("source_plugin"),
        valves_schema=export_data.get("valves_schema"),
    )
    db.add(new_pkg)
    await db.flush()  # 获取 new_pkg.id

    # 创建技能 / Create skills
    from app.enums.agent import SkillTypeEnum

    valid_skill_types = SkillTypeEnum.values()

    skills_created = 0
    for skill_data in skills_data:
        skill_type = skill_data.get("type", "toolkit")
        if skill_type not in valid_skill_types:
            logger.warning(
                "Skipping skill with invalid type '{}' during import of '{}'",
                skill_type,
                pkg_name,
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
        "Skill package imported: {} (id={}) with {} skills",
        pkg_name,
        new_pkg.id,
        skills_created,
    )

    return {
        "status": "created",
        "package_id": new_pkg.id,
        "package_name": pkg_name,
        "skills_created": skills_created,
    }
