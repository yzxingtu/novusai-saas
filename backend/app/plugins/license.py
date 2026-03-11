"""
Plugin License Key generation and verification / 插件 License Key 生成与验证

Offline verification scheme based on Ed25519 signatures.
Public key embedded in code, private key retained only on the generation side.
No network required to verify License Key authenticity.
/
基于 Ed25519 签名的离线验证方案。
公钥嵌入代码中，私钥仅在生成端保留。
无需联网即可验证 License Key 的真实性。

Key format / Key 格式: NOVUS-{base64_payload}.{base64_signature}
Payload: JSON { plugin, scope, buyer, issued_at }
"""

from __future__ import annotations

import base64
import json
import time
from typing import TYPE_CHECKING

from app.core.i18n import _
from app.core.logging import get_logger
from app.enums.plugin import PluginLicenseTypeEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# NovusAI platform Ed25519 public key (Base64 encoded)
# Private key only retained in License generation tool, not in codebase
# Override via NOVUSAI_LICENSE_PUBLIC_KEY env var if replacement needed
# / NovusAI 平台 Ed25519 公钥（Base64 编码）
# 私钥仅在 License 生成工具中保留，不入代码库
# 如需替换，通过环境变量 NOVUSAI_LICENSE_PUBLIC_KEY 覆盖
_DEFAULT_PUBLIC_KEY_B64 = ""  # 部署时配置


def _get_public_key_bytes() -> bytes | None:
    """Get Ed25519 public key bytes / 获取 Ed25519 公钥字节"""
    import os

    key_b64 = os.environ.get("NOVUSAI_LICENSE_PUBLIC_KEY", _DEFAULT_PUBLIC_KEY_B64)
    if not key_b64:
        return None
    try:
        return base64.b64decode(key_b64)
    except Exception:
        return None


def generate_license_key(
    plugin_name: str,
    version_scope: str = "*",
    buyer_email: str = "",
    private_key_b64: str = "",
    expires_days: int | None = None,
) -> str:
    """
    Generate License Key (internal tool only, not exposed in platform API).
    / 生成 License Key（仅内部工具使用，不暴露在平台 API）。

    Args:
        plugin_name: Plugin name / 插件名
        version_scope: Version range (e.g. ">=1.0.0" or "*") / 版本范围
        buyer_email: Buyer email / 购买者邮箱
        private_key_b64: Ed25519 private key (Base64 encoded) / Ed25519 私钥
        expires_days: Valid days (None = permanent) / 有效天数（None 表示永久）

    Returns:
        Formatted License Key: NOVUS-{payload_b64}.{signature_b64}
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if not private_key_b64:
        raise ValueError("Private key is required for license generation")

    private_key_bytes = base64.b64decode(private_key_b64)
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)

    now = int(time.time())
    payload: dict = {
        "plugin": plugin_name,
        "scope": version_scope,
        "buyer": buyer_email,
        "issued_at": now,
    }
    if expires_days is not None:
        payload["expires_at"] = now + expires_days * 86400

    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_bytes = payload_json.encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii")

    signature = private_key.sign(payload_bytes)
    signature_b64 = base64.urlsafe_b64encode(signature).decode("ascii")

    return f"NOVUS-{payload_b64}.{signature_b64}"


def verify_license_key(
    license_key: str,
    plugin_name: str,
) -> dict | None:
    """
    Verify License Key (local verification, no network required).
    / 验证 License Key（本地验证，无需联网）。

    Args:
        license_key: Format NOVUS-{payload_b64}.{signature_b64}
        plugin_name: Plugin name to verify / 要验证的插件名

    Returns:
        Payload dict on success, None on failure / 验证通过返回 payload dict，失败返回 None
    """
    if not license_key or not license_key.startswith("NOVUS-"):
        return None

    public_key_bytes = _get_public_key_bytes()
    if not public_key_bytes:
        from app.core.config import settings

        if settings.DEBUG:
            logger.warning("License verification skipped: no public key configured (DEBUG mode)")
            # Dev mode allows no-public-key compatibility / 开发模式允许无公钥兼容
            return _parse_payload_without_verify(license_key)

        # Production mode fail-close / 生产模式 fail-close
        logger.error("License verification failed: no public key configured")
        return None

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        body = license_key[6:]  # 去掉 "NOVUS-"
        if "." not in body:
            return None

        payload_b64, signature_b64 = body.rsplit(".", 1)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        signature_bytes = base64.urlsafe_b64decode(signature_b64)

        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature_bytes, payload_bytes)

        payload = json.loads(payload_bytes)

        # Check plugin name match / 检查插件名匹配
        if payload.get("plugin") != plugin_name:
            logger.warning(
                "License plugin mismatch: key=%s, expected=%s",
                payload.get("plugin"), plugin_name,
            )
            return None

        return payload

    except Exception as exc:
        logger.warning("License verification failed: %s", exc)
        return None


def _parse_payload_without_verify(license_key: str) -> dict | None:
    """Parse payload without verifying signature (used in dev mode / no public key) / 解析 payload 但不验证签名（开发模式/无公钥时使用）"""
    try:
        body = license_key[6:]
        if "." not in body:
            return None
        payload_b64 = body.rsplit(".", 1)[0]
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return None


async def activate_license(
    plugin_id: int,
    license_key: str,
    db: AsyncSession,
) -> dict:
    """
    Activate License Key.
    / 激活 License Key。

    Verify Key → write to PluginLicense table → update license_type.
    / 验证 Key → 写入 PluginLicense 表 → 更新 license_type。

    Returns:
        {"success": True/False, "message": "...", "license_info": {...}}
    """
    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    # Find plugin / 查找插件
    result = await db.execute(
        select(Plugin).where(
            Plugin.id == plugin_id,
            Plugin.is_deleted.is_(False),
        )
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        return {"success": False, "message": _("plugin.error.not_found")}

    # Verify License Key / 验证 License Key
    license_info = verify_license_key(license_key, plugin.name)
    if not license_info:
        return {"success": False, "message": _("plugin.error.license_invalid")}

    # Check if License Key already activated (prevent replay) / 检查 License Key 是否已被激活（防止重放）
    existing_license = await db.execute(
        select(PluginLicense).where(
            PluginLicense.license_key == license_key,
            PluginLicense.is_valid.is_(True),
        )
    )
    if existing_license.scalar_one_or_none():
        return {"success": False, "message": _("plugin.error.license_already_activated")}

    # Parse validity period / 解析有效期
    from datetime import datetime, timezone

    expires_at_ts = license_info.get("expires_at")
    expires_at_dt = None
    if expires_at_ts and isinstance(expires_at_ts, (int, float)):
        # utc_now() returns naive UTC; strip tz to keep consistent
        expires_at_dt = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc).replace(tzinfo=None)

    now = utc_now()

    # Check if Key has expired / 检查 Key 是否已过期
    if expires_at_dt and now >= expires_at_dt:
        return {"success": False, "message": _("plugin.error.license_expired")}

    # Invalidate old licenses / 使旧 license 失效
    from sqlalchemy import update

    await db.execute(
        update(PluginLicense).where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_valid.is_(True),
        ).values(is_valid=False)
    )

    # Write to PluginLicense table / 写入 PluginLicense 表
    license_record = PluginLicense(
        plugin_id=plugin_id,
        license_key=license_key,
        license_type=PluginLicenseTypeEnum.PERPETUAL.value,
        version_scope=license_info.get("scope", "*"),
        buyer_email=license_info.get("buyer", ""),
        issued_at=now,
        activated_at=now,
        expires_at=expires_at_dt,
        is_valid=True,
    )
    db.add(license_record)
    await db.flush()

    logger.info(
        "License activated for plugin %s (buyer=%s, expires=%s)",
        plugin.name, license_info.get("buyer"), expires_at_dt,
    )

    remaining_days = None
    if expires_at_dt:
        remaining_days = (expires_at_dt - now).days

    return {
        "success": True,
        "message": _("plugin.license_activated"),
        "license_info": {
            **license_info,
            "expires_at": str(expires_at_dt) if expires_at_dt else None,
            "remaining_days": remaining_days,
        },
    }


async def get_license_status_by_name(
    plugin_name: str,
    db: AsyncSession,
) -> dict:
    """
    Get License status by plugin name (for plugin license_gate AsyncSession path).
    / 通过插件名获取 License 状态（供插件 license_gate 的 AsyncSession 路径使用）。

    Returns:
        Dict consistent with PluginContext.get_own_license_status() format
        / 与 PluginContext.get_own_license_status() 返回格式一致的 dict
    """
    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    result = await db.execute(
        select(Plugin.id).where(
            Plugin.name == plugin_name,
            Plugin.is_deleted.is_(False),
        )
    )
    plugin_id = result.scalar_one_or_none()
    if not plugin_id:
        return {
            "status": "invalid",
            "license_type": None,
            "is_valid": False,
            "message": f"Plugin '{plugin_name}' not found",
        }

    lic_result = await db.execute(
        select(PluginLicense).where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_deleted.is_(False),
        ).order_by(PluginLicense.created_at.desc()).limit(1)
    )
    record = lic_result.scalars().first()
    if not record:
        return {
            "status": "invalid",
            "license_type": None,
            "is_valid": False,
            "message": "No license found",
        }

    now = utc_now()

    # Trial
    if record.license_type == PluginLicenseTypeEnum.TRIAL.value:
        if record.trial_expires_at and now < record.trial_expires_at:
            remaining = (record.trial_expires_at - now).days
            return {
                "status": "trial",
                "license_type": "trial",
                "is_valid": True,
                "trial_days_remaining": remaining,
                "expires_at": str(record.trial_expires_at),
            }
        return {
            "status": "expired",
            "license_type": "trial",
            "is_valid": False,
            "message": "Trial period expired",
        }

    # Paid — check expires_at
    if record.is_valid:
        if record.expires_at and now >= record.expires_at:
            return {
                "status": "expired",
                "license_type": record.license_type,
                "is_valid": False,
                "message": "License expired",
                "expires_at": str(record.expires_at),
            }
        remaining_days = None
        if record.expires_at:
            remaining_days = (record.expires_at - now).days
        return {
            "status": "active",
            "license_type": record.license_type,
            "is_valid": True,
            "license_key": _mask_key(record.license_key),
            "activated_at": str(record.activated_at) if record.activated_at else None,
            "expires_at": str(record.expires_at) if record.expires_at else None,
            "remaining_days": remaining_days,
        }

    return {
        "status": "expired",
        "license_type": record.license_type,
        "is_valid": False,
        "message": "License expired or revoked",
    }


def _mask_key(key: str | None) -> str:
    """Mask license key: NOVUS-xxxx...xxxx"""
    if not key or len(key) < 20:
        return "****"
    return f"{key[:10]}****{key[-4:]}"


async def create_trial_license(
    plugin_id: int,
    trial_days: int,
    db: AsyncSession,
) -> None:
    """Create trial License (auto-called when installing paid plugin without Key) / 创建试用 License（安装付费插件无 Key 时自动调用）"""
    from datetime import timedelta

    from app.core.base_model import utc_now
    from app.models.system.plugin_license import PluginLicense

    trial_expires = utc_now() + timedelta(days=trial_days)

    license_record = PluginLicense(
        plugin_id=plugin_id,
        license_key=None,
        license_type=PluginLicenseTypeEnum.TRIAL.value,
        is_valid=True,
        activated_at=utc_now(),
        trial_expires_at=trial_expires,
    )
    db.add(license_record)
    await db.flush()

    logger.info("Trial license created for plugin %d (%d days)", plugin_id, trial_days)


async def get_license_status_by_id(
    plugin_id: int,
    db: AsyncSession,
) -> dict:
    """
    Get License status by plugin ID (for Admin API use).
    / 通过插件 ID 获取 License 状态（供 Admin API 使用）。
    """
    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.models.system.plugin_license import PluginLicense

    lic_result = await db.execute(
        select(PluginLicense).where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_deleted.is_(False),
        ).order_by(PluginLicense.created_at.desc()).limit(1)
    )
    record = lic_result.scalars().first()
    if not record:
        return {
            "status": "none",
            "license_type": None,
            "is_valid": False,
            "message": "No license found",
        }

    now = utc_now()

    if record.license_type == PluginLicenseTypeEnum.TRIAL.value:
        if record.trial_expires_at and now < record.trial_expires_at:
            remaining = (record.trial_expires_at - now).days
            return {
                "status": "trial",
                "license_type": "trial",
                "is_valid": True,
                "trial_days_remaining": remaining,
                "expires_at": str(record.trial_expires_at),
                "activated_at": str(record.activated_at) if record.activated_at else None,
            }
        return {
            "status": "expired",
            "license_type": "trial",
            "is_valid": False,
            "message": "Trial period expired",
        }

    if record.is_valid:
        if record.expires_at and now >= record.expires_at:
            return {
                "status": "expired",
                "license_type": record.license_type,
                "is_valid": False,
                "message": "License expired",
                "expires_at": str(record.expires_at),
            }
        remaining_days = None
        if record.expires_at:
            remaining_days = (record.expires_at - now).days
        return {
            "status": "active",
            "license_type": record.license_type,
            "is_valid": True,
            "license_key": _mask_key(record.license_key),
            "activated_at": str(record.activated_at) if record.activated_at else None,
            "expires_at": str(record.expires_at) if record.expires_at else None,
            "remaining_days": remaining_days,
            "buyer_email": record.buyer_email,
        }

    return {
        "status": "expired",
        "license_type": record.license_type,
        "is_valid": False,
        "message": "License expired or revoked",
    }


async def revoke_license(
    plugin_id: int,
    db: AsyncSession,
) -> None:
    """Revoke all valid Licenses for a plugin / 撤销插件的所有有效 License"""
    from sqlalchemy import update

    from app.models.system.plugin_license import PluginLicense

    await db.execute(
        update(PluginLicense).where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_valid.is_(True),
        ).values(is_valid=False)
    )
    await db.flush()
    logger.info("All licenses revoked for plugin %d", plugin_id)


async def check_trial_expirations(db: AsyncSession) -> list[dict]:
    """
    Check trial expiration status (called by scheduled task).
    / 检查试用期到期情况（定时任务调用）。

    Returns:
        List of expired / about-to-expire plugins / 到期/即将到期的插件列表
    """
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.enums.plugin import PluginLicenseTypeEnum, PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    now = utc_now()
    warn_threshold = now + timedelta(days=3)

    # Query soon-to-expire and already-expired trial Licenses
    # / 查询即将到期和已到期的试用 License
    result = await db.execute(
        select(PluginLicense, Plugin.name, Plugin.status).join(
            Plugin, Plugin.id == PluginLicense.plugin_id,
        ).where(
            PluginLicense.license_type == PluginLicenseTypeEnum.TRIAL.value,
            PluginLicense.is_valid.is_(True),
            PluginLicense.trial_expires_at.isnot(None),
            Plugin.is_deleted.is_(False),
        )
    )
    rows = result.all()

    actions: list[dict] = []
    for license_rec, plugin_name, plugin_status in rows:
        if license_rec.trial_expires_at <= now:
            # Already expired → disable plugin / 已到期 → 禁用插件
            if plugin_status == PluginStatusEnum.ENABLED.value:
                from app.plugins.lifecycle import PluginLifecycle

                lifecycle = PluginLifecycle(db)
                try:
                    await lifecycle.disable(license_rec.plugin_id)
                    actions.append({
                        "plugin": plugin_name,
                        "action": "disabled",
                        "reason": "trial_expired",
                    })
                except Exception as exc:
                    logger.warning("Failed to disable expired plugin %s: %s", plugin_name, exc)
            license_rec.is_valid = False
            await db.flush()

        elif license_rec.trial_expires_at <= warn_threshold:
            # About to expire → send reminder / 即将到期 → 发提醒
            days_left = (license_rec.trial_expires_at - now).days
            actions.append({
                "plugin": plugin_name,
                "action": "warning",
                "days_left": days_left,
            })

    return actions
