"""
NovusDoc Pro License 门控辅助

提供统一的 license 校验函数，供 API handler 和 Socket.IO namespace 使用。
校验逻辑：查询插件 ID → 调用 license_service.get_license_status → 判断 is_valid。
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.license")

PLUGIN_NAME = "novusdoc-pro"


async def check_license_valid(db: Any) -> tuple[bool, dict[str, Any]]:
    """
    检查 novusdoc-pro 的 license 是否有效。

    Returns:
        (is_valid, license_info)
        - is_valid=True: license 有效（trial 或 active）
        - is_valid=False: license 无效/过期/不存在，license_info 含错误信息
    """
    if hasattr(db, "get_own_license_status"):
        license_info = await db.get_own_license_status()
    else:
        from sqlalchemy import select

        from app.models.system.plugin import Plugin
        result = await db.execute(
            select(Plugin.id).where(
                Plugin.name == PLUGIN_NAME,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin_id = result.scalar_one_or_none()
        if not plugin_id:
            return False, {
                "status": "invalid",
                "message": f"{PLUGIN_NAME} plugin not found",
            }

        from .license_service import get_license_status

        license_info = await get_license_status(db, plugin_id)
    is_valid = license_info.get("is_valid", False)

    if not is_valid:
        logger.warning(
            "license gate: denied — status=%s message=%s",
            license_info.get("status"), license_info.get("message", ""),
        )

    return is_valid, license_info


def license_required_error(license_info: dict[str, Any]) -> dict[str, Any]:
    """
    生成 license 门控失败的标准错误响应。

    Returns:
        dict 可直接作为 handler 返回值（api_dispatcher 会转为 403 JSONResponse）
    """
    status = license_info.get("status", "invalid")
    if status == "expired":
        message = "NovusDoc Pro license expired. Please renew to continue using Pro features."
    elif status == "trial" and not license_info.get("is_valid"):
        message = "NovusDoc Pro trial period has ended. Please activate a license."
    else:
        message = "NovusDoc Pro license required. Please activate a license to use Pro features."

    return {
        "error": message,
        "code": 4031,
        "status_code": 403,
        "license_status": status,
    }
