"""
技能包工具共享逻辑

admin/tenant 两端 update_package_valves 的公共流程提取。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.core.i18n import _
from app.exceptions import BusinessException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.base_service import BaseService


async def validate_and_update_valves(
    *,
    db: AsyncSession,
    service: BaseService,
    package_id: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    校验并更新技能包的 valves_config。

    Args:
        db: 数据库会话
        service: 已实例化的 SkillPackageService
        package_id: 技能包 ID
        data: 请求体 {"valves_config": {...}}

    Returns:
        包含 valves_schema 和 valves_config 的字典

    Raises:
        BusinessException: 技能包没有 valves_schema
        ValidationException: 配置值校验失败
    """
    pkg = await service.get_by_id(package_id)
    if not pkg:
        from app.exceptions import NotFoundException
        raise NotFoundException(message=_("skill_package.error.not_found"))

    if not pkg.valves_schema:
        raise BusinessException(
            message=_("skill_package.error.no_valves_schema"),
        )

    valves_config = data.get("valves_config", {})
    if not isinstance(valves_config, dict):
        raise ValidationException(
            message=_("skill_package.error.invalid_valves_config"),
            code=4001,
        )

    # 校验 required 字段是否存在
    schema = pkg.valves_schema or {}
    required_fields = schema.get("required", [])
    if required_fields:
        missing = [
            f for f in required_fields
            if f not in valves_config or valves_config[f] in (None, "")
        ]
        if missing:
            raise ValidationException(
                message=_("skill_package.error.valves_missing_required").format(
                    fields=", ".join(missing),
                ),
                code=4001,
            )

    updated = await service.update(package_id, {"valves_config": valves_config})
    await db.commit()

    return {
        "valves_schema": updated.valves_schema,
        "valves_config": updated.valves_config,
    }
