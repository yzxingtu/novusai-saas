"""
技能包工具共享逻辑

admin/tenant 两端 update_package_valves 的公共流程提取。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

import re

from app.core.i18n import _
from app.exceptions import BusinessException, ValidationException

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.core.base_service import BaseService

SECRET_MASK = "******"
_SECRET_RE = re.compile(
    r"\b(api_?key|secret|password|access_?token|auth_?token|apikey|private_?key)\b",
    re.IGNORECASE,
)


def _is_secret_key(key: str) -> bool:
    return bool(_SECRET_RE.search(key))


def mask_secret_values(
    valves_config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """对 valves_config 中的 secret 字段值替换为掩码，用于 GET 响应。"""
    if not valves_config:
        return valves_config
    result = dict(valves_config)
    for key, value in result.items():
        if _is_secret_key(key) and value and value != SECRET_MASK:
            result[key] = SECRET_MASK
    return result


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

    # 保留掩码字段的原值（用户未修改的 secret 字段不覆盖）
    existing_config = pkg.valves_config or {}
    for key, value in list(valves_config.items()):
        if value == SECRET_MASK and key in existing_config:
            valves_config[key] = existing_config[key]

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
