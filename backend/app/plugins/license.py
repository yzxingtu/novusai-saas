"""
插件 License Key 生成与验证

基于 Ed25519 签名的离线验证方案。
公钥嵌入代码中，私钥仅在生成端保留。
无需联网即可验证 License Key 的真实性。

Key 格式: NOVUS-{base64_payload}.{base64_signature}
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

# NovusAI 平台 Ed25519 公钥（Base64 编码）
# 私钥仅在 License 生成工具中保留，不入代码库
# 如需替换，通过环境变量 NOVUSAI_LICENSE_PUBLIC_KEY 覆盖
_DEFAULT_PUBLIC_KEY_B64 = ""  # 部署时配置


def _get_public_key_bytes() -> bytes | None:
    """获取 Ed25519 公钥字节"""
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
) -> str:
    """
    生成 License Key（仅内部工具使用，不暴露在平台 API）。

    Args:
        plugin_name: 插件名
        version_scope: 版本范围（如 ">=1.0.0" 或 "*"）
        buyer_email: 购买者邮箱
        private_key_b64: Ed25519 私钥（Base64 编码）

    Returns:
        格式化的 License Key: NOVUS-{payload_b64}.{signature_b64}
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    if not private_key_b64:
        raise ValueError("Private key is required for license generation")

    private_key_bytes = base64.b64decode(private_key_b64)
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)

    payload = {
        "plugin": plugin_name,
        "scope": version_scope,
        "buyer": buyer_email,
        "issued_at": int(time.time()),
    }
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
    验证 License Key（本地验证，无需联网）。

    Args:
        license_key: 格式 NOVUS-{payload_b64}.{signature_b64}
        plugin_name: 要验证的插件名

    Returns:
        验证通过返回 payload dict，失败返回 None
    """
    if not license_key or not license_key.startswith("NOVUS-"):
        return None

    public_key_bytes = _get_public_key_bytes()
    if not public_key_bytes:
        from app.core.config import settings

        if settings.DEBUG:
            logger.warning("License verification skipped: no public key configured (DEBUG mode)")
            # 开发模式允许无公钥兼容
            return _parse_payload_without_verify(license_key)

        # 生产模式 fail-close
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

        # 检查插件名匹配
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
    """解析 payload 但不验证签名（开发模式/无公钥时使用）"""
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
    db: "AsyncSession",
) -> dict:
    """
    激活 License Key。

    验证 Key → 写入 PluginLicense 表 → 更新 license_type。

    Returns:
        {"success": True/False, "message": "...", "license_info": {...}}
    """
    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    # 查找插件
    result = await db.execute(
        select(Plugin).where(
            Plugin.id == plugin_id,
            Plugin.is_deleted.is_(False),
        )
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        return {"success": False, "message": _("plugin.error.not_found")}

    # 验证 License Key
    license_info = verify_license_key(license_key, plugin.name)
    if not license_info:
        return {"success": False, "message": _("plugin.error.license_invalid")}

    # 检查 License Key 是否已被激活（防止重放）
    existing_license = await db.execute(
        select(PluginLicense).where(
            PluginLicense.license_key == license_key,
            PluginLicense.is_valid.is_(True),
        )
    )
    if existing_license.scalar_one_or_none():
        return {"success": False, "message": _("plugin.error.license_already_activated")}

    # 写入 PluginLicense 表
    license_record = PluginLicense(
        plugin_id=plugin_id,
        license_key=license_key,
        license_type=PluginLicenseTypeEnum.PERPETUAL.value,
        version_scope=license_info.get("scope", "*"),
        buyer_email=license_info.get("buyer", ""),
        issued_at=utc_now(),
        activated_at=utc_now(),
        is_valid=True,
    )
    db.add(license_record)
    await db.flush()

    logger.info(
        "License activated for plugin %s (buyer=%s)",
        plugin.name, license_info.get("buyer"),
    )

    return {
        "success": True,
        "message": _("plugin.license_activated"),
        "license_info": license_info,
    }


async def create_trial_license(
    plugin_id: int,
    trial_days: int,
    db: "AsyncSession",
) -> None:
    """创建试用 License（安装付费插件无 Key 时自动调用）"""
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


async def check_trial_expirations(db: "AsyncSession") -> list[dict]:
    """
    检查试用期到期情况（定时任务调用）。

    Returns:
        到期/即将到期的插件列表
    """
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.enums.plugin import PluginLicenseTypeEnum, PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    now = utc_now()
    warn_threshold = now + timedelta(days=3)

    # 查询即将到期和已到期的试用 License
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
            # 已到期 → 禁用插件
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
            # 即将到期 → 发提醒
            days_left = (license_rec.trial_expires_at - now).days
            actions.append({
                "plugin": plugin_name,
                "action": "warning",
                "days_left": days_left,
            })

    return actions
