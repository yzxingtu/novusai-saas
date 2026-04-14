"""
Internal normalization helpers for AI call log repository.
AI 调用日志 Repository 内部规范化辅助函数。
"""

from __future__ import annotations

from datetime import datetime
from datetime import timezone as dt_timezone

from app.enums.log import UserTypeEnum as LogUserTypeEnum


def normalize_optional_int(value: object, *, allow_zero: bool = False) -> int | None:
    """Accept only real integer identifiers and ignore test doubles / 仅接受真实整数 ID，忽略测试替身。"""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or (value == 0 and not allow_zero):
        return None
    return value


def normalize_actor_type(
    actor_user_type: str | None,
    legacy_user_type: str | None,
) -> str | None:
    if actor_user_type and str(actor_user_type).strip():
        return str(actor_user_type).strip()
    if legacy_user_type == LogUserTypeEnum.ADMIN.value:
        return "platform_admin"
    if legacy_user_type == LogUserTypeEnum.TENANT_ADMIN.value:
        return "tenant_admin"
    if legacy_user_type == LogUserTypeEnum.TENANT_USER.value:
        return "tenant_user"
    return legacy_user_type


def actor_type_fallback_name(actor_type: str | None) -> str:
    return {
        "platform_admin": "平台管理员",
        "tenant_admin": "企业管理员",
        "tenant_user": "企业用户",
        LogUserTypeEnum.ADMIN.value: "平台管理员",
        LogUserTypeEnum.TENANT_ADMIN.value: "企业管理员",
        LogUserTypeEnum.TENANT_USER.value: "企业用户",
    }.get(actor_type or "", "-")


def display_name(nickname: str | None, username: str | None, fallback: str) -> str:
    if nickname and str(nickname).strip():
        return str(nickname).strip()
    if username and str(username).strip():
        return str(username).strip()
    return fallback


def normalize_caller_snapshot(metadata: object) -> dict[str, object]:
    if not isinstance(metadata, dict):
        return {}
    snapshot = metadata.get("caller_snapshot")
    if isinstance(snapshot, dict):
        return snapshot
    return {}


def datetime_to_iso_utc_str(value: object) -> object:
    """
    与 BaseSchema 一致：DB naive UTC -> 带时区 ISO，避免 JSON 输出无后缀时被浏览器当作本地时间解析。
    Align with BaseSchema: naive UTC -> timezone-aware ISO for correct browser local display.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_timezone.utc).isoformat()
        return value.isoformat()
    return value


def normalize_call_log_dict_datetimes(payload: dict) -> None:
    """就地规范化 API 中的时间字段 / Normalize datetime fields in-place for JSON API."""
    for key in ("created_at", "updated_at", "deleted_at"):
        if key in payload:
            payload[key] = datetime_to_iso_utc_str(payload[key])


def effective_item_tenant_id(item: object) -> int | None:
    billing_tenant_id = normalize_optional_int(
        getattr(item, "billing_tenant_id", None),
        allow_zero=True,
    )
    if billing_tenant_id is not None:
        return billing_tenant_id

    tenant_id = getattr(item, "tenant_id", None)
    if tenant_id is None:
        return None
    return normalize_optional_int(tenant_id, allow_zero=True)


__all__ = [
    "actor_type_fallback_name",
    "datetime_to_iso_utc_str",
    "display_name",
    "effective_item_tenant_id",
    "normalize_actor_type",
    "normalize_call_log_dict_datetimes",
    "normalize_caller_snapshot",
    "normalize_optional_int",
]
