"""
技能包工具箱（Valves）管理共享逻辑 / Skill Package Toolkit (Valves) Management Shared Logic

admin/tenant 两端 toolkit 端点共用的工具函数。
Utility functions shared by admin/tenant toolkit endpoints.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

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
    """
    将 valves_config 中标记为秘密的值替换为脱敏形式 / Mask secret values in valves_config.

    用于 GET 接口返回时隐藏敏感信息。
    Used to hide sensitive information in GET endpoint responses.
    """
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
    Validate and update skill package's valves_config.

    处理逻辑 / Processing logic:
    1. 检查技能包是否定义了 valves_schema / Check if package has valves_schema defined
    2. 校验必填参数 / Validate required parameters
    3. 处理秘密字段的“不改写”逻辑 / Handle secret field "no-overwrite" logic
    4. 持久化到 DB / Persist to DB
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

    # 保留掩码字段的原值（用户未修改的 secret 字段不覆盖） / Retain original values for masked fields (unmodified secret fields are not overwritten)
    existing_config = pkg.valves_config or {}
    for key, value in list(valves_config.items()):
        # 步骤3: 处理秘密字段（如果提交的值 == MASK_VALUE，保留原值） / Step 3: handle secret fields (if submitted value == MASK_VALUE, retain original)
        if value == SECRET_MASK and key in existing_config:
            valves_config[key] = existing_config[key]

    # 校验 required 字段是否存在 / Validate required fields exist
    schema = pkg.valves_schema or {}
    required_fields = schema.get("required", [])
    if required_fields:
        missing = [
            f
            for f in required_fields
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
