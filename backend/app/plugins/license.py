"""
Plugin License Key generation, status resolution, and runtime gating.
/
插件 License Key 生成、状态解析与运行时闸门。

Offline verification scheme based on Ed25519 signatures.
Public key embedded in code, private key retained only on the generation side.
No network required to verify License Key authenticity.
/
基于 Ed25519 签名的离线验证方案。
公钥嵌入代码中，私钥仅在生成端保留。
无需联网即可验证 License Key 的真实性。

Key format / Key 格式: NOVUS-{base64_payload}.{base64_signature}
Payload: JSON { plugin, scope, buyer, issued_at, expires_at? }
"""

from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import serialize_datetime_for_api
from app.enums.plugin import PluginLicenseTypeEnum, PluginPricingTypeEnum
from app.plugins.exceptions import PluginLicenseError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# NovusAI platform Ed25519 public key (Base64 encoded)
# Private key only retained in License generation tool, not in codebase
# Override via NOVUSAI_LICENSE_PUBLIC_KEY env var if replacement needed
# / NovusAI 平台 Ed25519 公钥（Base64 编码）
# 私钥仅在 License 生成工具中保留，不入代码库
# 如需替换，通过环境变量 NOVUSAI_LICENSE_PUBLIC_KEY 覆盖
_DEFAULT_PUBLIC_KEY_B64 = ""  # 部署时配置 / set in deployment

_LICENSE_STATE_RANK = {"active": 0, "expired": 1, "revoked": 2}
_TRIAL = PluginLicenseTypeEnum.TRIAL.value


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
    payload: dict[str, Any] = {
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
            logger.warning(
                "License verification skipped: no public key configured (DEBUG mode)"
            )
            payload = _parse_payload_without_verify(license_key)
            if payload and payload.get("plugin") == plugin_name:
                return payload
            logger.warning(
                "License debug fallback rejected: plugin mismatch (expected={}, payload={})",
                plugin_name,
                (payload or {}).get("plugin"),
            )
            return None

        logger.error("License verification failed: no public key configured")
        return None

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        body = license_key[6:]
        if "." not in body:
            return None

        payload_b64, signature_b64 = body.rsplit(".", 1)
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        signature_bytes = base64.urlsafe_b64decode(signature_b64)

        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature_bytes, payload_bytes)

        payload = json.loads(payload_bytes)
        if payload.get("plugin") != plugin_name:
            logger.warning(
                "License plugin mismatch: key={}, expected={}",
                payload.get("plugin"),
                plugin_name,
            )
            return None

        return payload

    except Exception as exc:
        logger.warning("License verification failed: {}", exc)
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


def _fmt_dt(dt: datetime | None) -> str | None:
    return serialize_datetime_for_api(dt)


def _mask_key(key: str | None) -> str:
    """Mask license key: NOVUS-xxxx...xxxx / 脱敏许可证 key：NOVUS-xxxx...xxxx"""
    if not key or len(key) < 20:
        return "****"
    return f"{key[:10]}****{key[-4:]}"


def _to_naive_utc(value: datetime | float | int | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).replace(tzinfo=None)
    return None


def _resolve_paid_license_type(expires_at: datetime | None) -> str:
    return (
        PluginLicenseTypeEnum.FIXED_TERM.value
        if expires_at is not None
        else PluginLicenseTypeEnum.PERPETUAL.value
    )


def _record_effective_expires_at(record: Any) -> datetime | None:
    if getattr(record, "license_type", None) == _TRIAL:
        return _to_naive_utc(getattr(record, "trial_expires_at", None))
    return _to_naive_utc(getattr(record, "expires_at", None))


def _record_runtime_state(record: Any, now: datetime) -> str:
    if not bool(getattr(record, "is_valid", False)):
        return "revoked"

    expires_at = _record_effective_expires_at(record)
    if expires_at and now >= expires_at:
        return "expired"
    return "active"


def _record_sort_key(record: Any, now: datetime) -> tuple[Any, ...]:
    state = _record_runtime_state(record, now)
    is_trial = getattr(record, "license_type", None) == _TRIAL
    activated_at = _to_naive_utc(getattr(record, "activated_at", None))
    created_at = _to_naive_utc(getattr(record, "created_at", None))
    issued_at = _to_naive_utc(getattr(record, "issued_at", None))
    sort_dt = activated_at or created_at or issued_at
    sort_ts = -(sort_dt.timestamp() if sort_dt else 0)
    record_id = -int(getattr(record, "id", 0) or 0)
    return (_LICENSE_STATE_RANK[state], 1 if is_trial else 0, sort_ts, record_id)


def _build_license_status(record: Any | None, *, now: datetime) -> dict[str, Any]:
    if not record:
        return {
            "status": "none",
            "license_type": None,
            "is_valid": False,
            "runtime_allowed": False,
            "message": "No license found",
        }

    license_type = getattr(record, "license_type", None)
    state = _record_runtime_state(record, now)
    expires_at = _record_effective_expires_at(record)
    activated_at = _to_naive_utc(getattr(record, "activated_at", None))
    remaining_days = None
    if expires_at and state == "active":
        remaining_days = max(0, (expires_at - now).days)

    buyer_email = getattr(record, "buyer_email", None)
    license_key = getattr(record, "license_key", None)
    version_scope = getattr(record, "version_scope", None)

    status = "trial" if license_type == _TRIAL and state == "active" else state
    payload: dict[str, Any] = {
        "status": status,
        "license_type": license_type,
        "is_valid": state == "active",
        "runtime_allowed": state == "active",
        "activated_at": _fmt_dt(activated_at),
        "expires_at": _fmt_dt(expires_at),
        "remaining_days": remaining_days,
        "buyer_email": buyer_email,
        "version_scope": version_scope,
    }

    if state == "active":
        if license_type == _TRIAL:
            payload["trial_days_remaining"] = remaining_days
        elif license_key:
            payload["license_key"] = _mask_key(license_key)
        return payload

    if state == "expired":
        payload["message"] = (
            "Trial period expired" if license_type == _TRIAL else "License expired"
        )
        return payload

    payload["message"] = "License revoked"
    return payload


async def _load_plugin_license_records(
    plugin_id: int,
    db: AsyncSession,
) -> list[Any]:
    from sqlalchemy import select

    from app.models.system.plugin_license import PluginLicense

    result = await db.execute(
        select(PluginLicense).where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_deleted.is_(False),
        )
    )
    return list(result.scalars().all())


async def get_preferred_license_record(
    plugin_id: int,
    db: AsyncSession,
) -> Any | None:
    """
    Pick the best runtime-relevant license record.
    / 选出当前最适合反映运行时状态的 License 记录。

    Priority:
    1. Active records before expired/revoked
    2. Paid records before trial records
    3. Newer activated/created records before older records
    / 优先级：
    1. 有效记录优先于已过期/已撤销
    2. 正式授权优先于试用
    3. 最近激活/创建优先于旧记录
    """
    from app.core.base_model import utc_now

    records = await _load_plugin_license_records(plugin_id, db)
    if not records:
        return None

    now = utc_now()
    return min(records, key=lambda record: _record_sort_key(record, now))


async def get_effective_license_status(
    plugin_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    from app.core.base_model import utc_now

    record = await get_preferred_license_record(plugin_id, db)
    return _build_license_status(record, now=utc_now())


async def get_license_status_by_name(
    plugin_name: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Get license status by plugin name.
    / 通过插件名获取 License 状态。
    """
    from sqlalchemy import select

    from app.models.system.plugin import Plugin

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
            "runtime_allowed": False,
            "message": f"Plugin '{plugin_name}' not found",
        }

    return await get_effective_license_status(plugin_id, db)


async def get_license_status_by_id(
    plugin_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Get license status by plugin ID.
    / 通过插件 ID 获取 License 状态。
    """
    return await get_effective_license_status(plugin_id, db)


async def get_plugin_runtime_license_status(
    plugin_id: int,
    pricing_type: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Return runtime license state; free plugins are always allowed.
    / 返回运行时 License 状态；免费插件默认可运行。
    """
    if pricing_type != PluginPricingTypeEnum.PAID.value:
        return {
            "status": "not_required",
            "license_type": None,
            "is_valid": True,
            "runtime_allowed": True,
            "message": "Free plugin does not require license",
        }

    return await get_effective_license_status(plugin_id, db)


async def assert_plugin_license_active(
    plugin_id: int,
    pricing_type: str,
    db: AsyncSession,
    *,
    plugin_name: str = "",
    operation: str = "run",
) -> dict[str, Any]:
    """
    Enforce runtime license gate for paid plugins.
    / 对付费插件执行统一运行时 License 闸门。
    """
    status = await get_plugin_runtime_license_status(plugin_id, pricing_type, db)
    if status.get("runtime_allowed"):
        return status

    plugin_label = plugin_name or f"#{plugin_id}"
    message = status.get("message") or _("plugin.error.license_invalid")
    raise PluginLicenseError(
        message=(
            f"Plugin '{plugin_label}' cannot {operation}: {message}. "
            "License controls whether the host platform allows the plugin to run."
        ),
    )


async def activate_license(
    plugin_id: int,
    license_key: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Activate a paid License Key.
    / 激活正式 License Key。

    Semantics:
    - trial: temporary trial
    - fixed_term: paid license with expires_at
    - perpetual: paid license without expires_at
    / 语义：
    - trial：试用
    - fixed_term：带期限正式授权
    - perpetual：永久正式授权
    """
    from sqlalchemy import select, update

    from app.core.base_model import utc_now
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    result = await db.execute(
        select(Plugin).where(
            Plugin.id == plugin_id,
            Plugin.is_deleted.is_(False),
        )
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        return {"success": False, "message": _("plugin.error.not_found")}

    if plugin.pricing_type != PluginPricingTypeEnum.PAID.value:
        return {
            "success": False,
            "message": "Free plugins do not accept paid license activation",
        }

    license_info = verify_license_key(license_key, plugin.name)
    if not license_info:
        return {"success": False, "message": _("plugin.error.license_invalid")}

    existing_license = await db.execute(
        select(PluginLicense.id).where(
            PluginLicense.license_key == license_key,
            PluginLicense.is_deleted.is_(False),
        )
    )
    if existing_license.scalar_one_or_none():
        return {
            "success": False,
            "message": _("plugin.error.license_already_activated"),
        }

    now = utc_now()
    expires_at_dt = _to_naive_utc(license_info.get("expires_at"))
    if expires_at_dt and now >= expires_at_dt:
        return {"success": False, "message": _("plugin.error.license_expired")}

    await db.execute(
        update(PluginLicense)
        .where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_valid.is_(True),
        )
        .values(is_valid=False)
    )

    license_record = PluginLicense(
        plugin_id=plugin_id,
        license_key=license_key,
        license_type=_resolve_paid_license_type(expires_at_dt),
        version_scope=license_info.get("scope", "*"),
        buyer_email=license_info.get("buyer", ""),
        issued_at=_to_naive_utc(license_info.get("issued_at")) or now,
        activated_at=now,
        expires_at=expires_at_dt,
        is_valid=True,
    )
    db.add(license_record)
    await db.flush()

    status = await get_effective_license_status(plugin_id, db)
    logger.info(
        "License activated for plugin {} (type={}, buyer={}, expires={})",
        plugin.name,
        license_record.license_type,
        license_record.buyer_email,
        expires_at_dt,
    )
    return {
        "success": True,
        "message": _("plugin.license_activated"),
        "license_info": status,
    }


async def create_trial_license(
    plugin_id: int,
    db: AsyncSession,
) -> dict[str, Any]:
    """Create a one-time trial license driven by manifest.pricing.trial. / 按 manifest.pricing.trial 发放一次性试用授权。"""
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    result = await db.execute(
        select(Plugin).where(
            Plugin.id == plugin_id,
            Plugin.is_deleted.is_(False),
        )
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise PluginLicenseError(message=_("plugin.error.not_found"))

    if plugin.pricing_type != PluginPricingTypeEnum.PAID.value:
        raise PluginLicenseError(message="Free plugins cannot start a trial")

    manifest_data = plugin.manifest or {}
    pricing = (
        manifest_data.get("pricing", {}) if isinstance(manifest_data, dict) else {}
    )
    trial_cfg = pricing.get("trial", {}) if isinstance(pricing, dict) else {}
    trial_enabled = bool(trial_cfg.get("enabled"))
    trial_days = int(trial_cfg.get("days") or 0)

    if not trial_enabled or trial_days <= 0:
        raise PluginLicenseError(message="Trial is disabled for this plugin")

    records = await _load_plugin_license_records(plugin_id, db)
    if any(getattr(record, "license_type", None) == _TRIAL for record in records):
        raise PluginLicenseError(
            message="Trial has already been issued for this plugin"
        )
    if any(getattr(record, "license_type", None) != _TRIAL for record in records):
        raise PluginLicenseError(
            message="Paid license already exists, trial is not allowed"
        )

    now = utc_now()
    trial_expires = now + timedelta(days=trial_days)

    db.add(
        PluginLicense(
            plugin_id=plugin_id,
            license_key=None,
            license_type=_TRIAL,
            is_valid=True,
            activated_at=now,
            trial_expires_at=trial_expires,
        )
    )
    await db.flush()

    logger.info(
        "Trial license created for plugin {} ({} days)",
        plugin.name,
        trial_days,
    )
    return await get_effective_license_status(plugin_id, db)


async def revoke_license(
    plugin_id: int,
    db: AsyncSession,
) -> None:
    """Revoke all active licenses for a plugin / 撤销插件全部有效 License"""
    from sqlalchemy import update

    from app.models.system.plugin_license import PluginLicense

    await db.execute(
        update(PluginLicense)
        .where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_valid.is_(True),
        )
        .values(is_valid=False)
    )
    await db.flush()
    logger.info("All licenses revoked for plugin {}", plugin_id)


async def check_plugin_license_expirations(db: AsyncSession) -> list[dict[str, Any]]:
    """
    Check both trial and fixed-term license expirations.
    / 统一检查 trial 与 fixed-term License 到期情况。
    """
    from datetime import timedelta

    from sqlalchemy import select

    from app.core.base_model import utc_now
    from app.enums.plugin import PluginStatusEnum
    from app.models.system.plugin import Plugin
    from app.models.system.plugin_license import PluginLicense

    now = utc_now()
    warn_threshold = now + timedelta(days=3)

    result = await db.execute(
        select(PluginLicense, Plugin.name, Plugin.status)
        .join(
            Plugin,
            Plugin.id == PluginLicense.plugin_id,
        )
        .where(
            PluginLicense.is_valid.is_(True),
            PluginLicense.is_deleted.is_(False),
            Plugin.is_deleted.is_(False),
        )
    )
    rows = result.all()

    actions: list[dict[str, Any]] = []
    for license_rec, plugin_name, plugin_status in rows:
        expires_at = _record_effective_expires_at(license_rec)
        if not expires_at:
            continue

        if expires_at <= now:
            if plugin_status == PluginStatusEnum.ENABLED.value:
                from app.plugins.lifecycle import PluginLifecycle

                lifecycle = PluginLifecycle(db)
                try:
                    await lifecycle.disable(license_rec.plugin_id)
                    actions.append(
                        {
                            "plugin": plugin_name,
                            "action": "disabled",
                            "reason": "license_expired",
                            "license_type": getattr(license_rec, "license_type", None),
                        }
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to disable expired plugin {}: {}",
                        plugin_name,
                        exc,
                    )
            license_rec.is_valid = False
            await db.flush()
            continue

        if expires_at <= warn_threshold:
            actions.append(
                {
                    "plugin": plugin_name,
                    "action": "warning",
                    "license_type": getattr(license_rec, "license_type", None),
                    "days_left": max(0, (expires_at - now).days),
                }
            )

    return actions
