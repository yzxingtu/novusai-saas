"""Storage billing period helpers. / 对象存储计费账期辅助函数。"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.base_model import utc_now
from app.core.i18n import _
from app.exceptions import BusinessException

from .models import StorageBillingPeriodTypeEnum

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _normalize_raw_date(raw_value: object | None) -> str | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, date):
        return raw_value.isoformat()

    normalized = str(raw_value).strip()
    return normalized or None


def _parse_iso_date_or_raise(raw_value: object | None, *, message: str) -> date | None:
    normalized = _normalize_raw_date(raw_value)
    if normalized is None:
        return None

    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise BusinessException(message=message) from exc


def parse_optional_billing_date(raw_value: Any) -> date | None:
    """Parse optional billing_date in YYYY-MM-DD format. / 解析可选 billing_date。"""
    return _parse_iso_date_or_raise(
        raw_value,
        message=_("billing_date must use YYYY-MM-DD format."),
    )


def resolve_billing_date(
    raw_value: object | None,
    *,
    default_offset_days: int = 1,
) -> date:
    """Resolve billing_date with default lag fallback. / 解析 billing_date，空值时回退到默认滞后日。"""
    parsed = parse_optional_billing_date(raw_value)
    if parsed is not None:
        return parsed
    return (utc_now().astimezone(SHANGHAI_TZ) - timedelta(days=default_offset_days)).date()


def parse_optional_billing_month(raw_value: Any) -> date | None:
    """Parse optional billing_month in YYYY-MM or YYYY-MM-DD format. / 解析可选 billing_month。"""
    normalized = _normalize_raw_date(raw_value)
    if normalized is None:
        return None
    if len(normalized) == 7:
        normalized = f"{normalized}-01"

    parsed = _parse_iso_date_or_raise(
        normalized,
        message=_("billing_month must use YYYY-MM or YYYY-MM-DD format."),
    )
    if parsed is None:
        return None
    return parsed.replace(day=1)


def parse_optional_period_type(raw_value: Any) -> str | None:
    """Parse optional period_type enum. / 解析可选 period_type 枚举值。"""
    normalized = str(raw_value or "").strip()
    if not normalized:
        return None
    if not StorageBillingPeriodTypeEnum.has_value(normalized):
        raise BusinessException(message=_("period_type must be one of: daily, monthly."))
    return normalized


def resolve_billing_month(raw_value: object | None) -> date:
    """Resolve billing_month with previous-month fallback. / 解析 billing_month，空值时回退到上月。"""
    parsed = parse_optional_billing_month(raw_value)
    if parsed is not None:
        return parsed

    today = utc_now().astimezone(SHANGHAI_TZ).date()
    return (today.replace(day=1) - timedelta(days=1)).replace(day=1)
