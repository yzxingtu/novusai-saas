"""
Backward-compatible license service for novusdoc-pro.

This module keeps the old import path (`services.license_service`) working.
New code should prefer `services.license_gate`.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from sqlalchemy import select

from app.core.base_model import utc_now
from app.enums.plugin import PluginLicenseTypeEnum
from app.models.system.plugin_license import PluginLicense


class LicenseStatus(str, Enum):
    """Legacy status enum kept for compatibility."""

    INVALID = "invalid"
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"


def _mask_key(key: str | None) -> str:
    if not key or len(key) < 20:
        return "****"
    return f"{key[:10]}****{key[-4:]}"


async def get_license_status(db: Any, plugin_id: int) -> dict[str, Any]:
    """
    Read latest license status for the given plugin.

    Uses `.first()` on scalar results to avoid `scalar_one_or_none()` instability
    when multiple historical rows exist.
    """
    result = await db.execute(
        select(PluginLicense).where(
            PluginLicense.plugin_id == plugin_id,
            PluginLicense.is_deleted.is_(False),
        ).order_by(PluginLicense.created_at.desc()).limit(1)
    )
    record = result.scalars().first()
    if not record:
        return {
            "status": LicenseStatus.INVALID,
            "license_type": None,
            "is_valid": False,
            "message": "No license found",
        }

    now = utc_now()
    license_type = getattr(record, "license_type", None)
    is_valid = bool(getattr(record, "is_valid", False))
    trial_expires_at = getattr(record, "trial_expires_at", None)
    expires_at = getattr(record, "expires_at", None)
    activated_at = getattr(record, "activated_at", None)
    license_key = getattr(record, "license_key", None)

    if license_type == PluginLicenseTypeEnum.TRIAL.value:
        if trial_expires_at and now < trial_expires_at:
            return {
                "status": LicenseStatus.TRIAL,
                "license_type": license_type,
                "is_valid": True,
                "trial_days_remaining": (trial_expires_at - now).days,
                "expires_at": str(trial_expires_at),
            }
        return {
            "status": LicenseStatus.EXPIRED,
            "license_type": license_type,
            "is_valid": False,
            "message": "Trial period expired",
        }

    if is_valid:
        if expires_at and now >= expires_at:
            return {
                "status": LicenseStatus.EXPIRED,
                "license_type": license_type,
                "is_valid": False,
                "message": "License expired",
                "expires_at": str(expires_at),
            }
        remaining_days = (expires_at - now).days if expires_at else None
        return {
            "status": LicenseStatus.ACTIVE,
            "license_type": license_type,
            "is_valid": True,
            "license_key": _mask_key(license_key),
            "activated_at": str(activated_at) if activated_at else None,
            "expires_at": str(expires_at) if expires_at else None,
            "remaining_days": remaining_days,
        }

    return {
        "status": LicenseStatus.EXPIRED,
        "license_type": license_type,
        "is_valid": False,
        "message": "License expired or revoked",
    }


__all__ = ["LicenseStatus", "get_license_status"]
