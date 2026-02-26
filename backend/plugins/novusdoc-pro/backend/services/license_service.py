"""
NovusDoc Pro License 门控服务

验证 License Key（在线/离线）、试用期逻辑、到期降级。

License Key 格式:
  NDOC-STD-XXXX-XXXX-XXXX-XXXX  (Standard 无源码)
  NDOC-SRC-XXXX-XXXX-XXXX-XXXX  (Source 有源码)

验证方式:
  A. 在线验证: POST License Server → 绑定实例 → 缓存 72h
  B. 离线验证: Ed25519 签名本地验证
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.core.base_model import utc_now
from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.license")

TRIAL_DAYS = 14
CACHE_TTL_HOURS = 72
HEARTBEAT_INTERVAL_DAYS = 7


class LicenseStatus:
    """License 状态枚举"""

    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALID = "invalid"


async def get_license_status(db: Any, plugin_id: int) -> dict[str, Any]:
    """
    获取插件的 License 状态。

    Returns:
        {status, license_type, expires_at, trial_days_remaining, is_valid}
    """
    from sqlalchemy import select
    from app.models.system.plugin_license import PluginLicense

    result = await db.execute(
        select(PluginLicense).where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_deleted.is_(False),
        ).order_by(PluginLicense.created_at.desc()).limit(1)
    )
    license_record = result.scalars().first()

    if not license_record:
        return {
            "status": LicenseStatus.INVALID,
            "license_type": None,
            "is_valid": False,
            "message": "No license found",
        }

    now = utc_now()

    # Trial license
    if license_record.license_type == "trial":
        if license_record.trial_expires_at and now < license_record.trial_expires_at:
            remaining = (license_record.trial_expires_at - now).days
            return {
                "status": LicenseStatus.TRIAL,
                "license_type": "trial",
                "is_valid": True,
                "trial_days_remaining": remaining,
                "expires_at": str(license_record.trial_expires_at),
            }
        else:
            return {
                "status": LicenseStatus.EXPIRED,
                "license_type": "trial",
                "is_valid": False,
                "message": "Trial period expired",
            }

    # Paid license
    if license_record.is_valid:
        return {
            "status": LicenseStatus.ACTIVE,
            "license_type": license_record.license_type,
            "is_valid": True,
            "license_key": _mask_key(license_record.license_key),
            "activated_at": str(license_record.activated_at) if license_record.activated_at else None,
        }

    return {
        "status": LicenseStatus.EXPIRED,
        "license_type": license_record.license_type,
        "is_valid": False,
        "message": "License expired or revoked",
    }


async def activate_trial(db: Any, plugin_id: int) -> dict[str, Any]:
    """激活 14 天试用"""
    from app.models.system.plugin_license import PluginLicense

    now = utc_now()
    trial_expires = now + timedelta(days=TRIAL_DAYS)

    license_record = PluginLicense(
        plugin_id=plugin_id,
        license_type="trial",
        trial_expires_at=trial_expires,
        activated_at=now,
        is_valid=True,
    )
    db.add(license_record)
    await db.flush()

    logger.info("license: trial activated for plugin %d, expires %s", plugin_id, trial_expires)

    return {
        "status": LicenseStatus.TRIAL,
        "trial_days_remaining": TRIAL_DAYS,
        "expires_at": str(trial_expires),
    }


async def activate_license_key(
    db: Any,
    plugin_id: int,
    license_key: str,
    buyer_email: str = "",
) -> dict[str, Any]:
    """
    激活 License Key（在线验证 stub）。

    实际实现需要 POST 到 License Server 验证 Key 有效性。
    当前为 stub，接受任何 NDOC-* 格式的 Key。
    """
    from app.models.system.plugin_license import PluginLicense

    if not license_key.startswith("NDOC-"):
        return {"error": "Invalid license key format", "is_valid": False}

    # 确定 license type
    if license_key.startswith("NDOC-STD-"):
        license_type = "standard"
    elif license_key.startswith("NDOC-SRC-"):
        license_type = "source"
    else:
        license_type = "standard"

    now = utc_now()

    license_record = PluginLicense(
        plugin_id=plugin_id,
        license_key=license_key,
        license_type=license_type,
        buyer_email=buyer_email,
        activated_at=now,
        issued_at=now,
        is_valid=True,
    )
    db.add(license_record)
    await db.flush()

    logger.info("license: key activated for plugin %d, type=%s", plugin_id, license_type)

    return {
        "status": LicenseStatus.ACTIVE,
        "license_type": license_type,
        "is_valid": True,
        "license_key": _mask_key(license_key),
    }


def _mask_key(key: str | None) -> str:
    """Mask license key for display: NDOC-STD-XXXX-****-****-XXXX"""
    if not key or len(key) < 20:
        return "****"
    return f"{key[:9]}****-****-{key[-4:]}"
