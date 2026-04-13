"""Normalization helpers for AI action log payloads."""

import inspect
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from unittest.mock import AsyncMock

from app.core.base_model import BaseModel
from app.core.identity_snapshot import normalize_identity_snapshot_user_type
from app.core.response import serialize_datetime_for_api
from app.enums.agent import ActionLevelEnum


def resolve_action_level(
    action_name: str,
    *,
    default: str = ActionLevelEnum.SAFE_WRITE.value,
) -> str:
    """
    根据动作名推断安全等级 / Infer action level from action name.
    """
    normalized = (action_name or "").strip().lower()
    if normalized.startswith(("delete", "remove", "drop")):
        return ActionLevelEnum.DANGEROUS.value
    if normalized.startswith(("get", "list", "read", "search", "view", "refresh")):
        return ActionLevelEnum.READ.value
    return default


def _normalize_operator_type(operator_type: str | None) -> str | None:
    return normalize_identity_snapshot_user_type(operator_type)


def _normalize_audit_value(value: Any) -> Any:
    """
    Normalize audit payload values to JSON-safe structures.
    将审计日志值规范化为 JSON 安全结构。
    """
    if value is None or isinstance(value, (bool, float, int, str)):
        return value

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, datetime):
        return serialize_datetime_for_api(value)

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, BaseModel):
        return {
            key: _normalize_audit_value(item) for key, item in value.to_dict().items()
        }

    if is_dataclass(value) and not isinstance(value, type):
        return _normalize_audit_value(asdict(value))

    if isinstance(value, dict):
        return {str(key): _normalize_audit_value(item) for key, item in value.items()}

    if isinstance(value, (list, set, tuple)):
        return [_normalize_audit_value(item) for item in value]

    model_dump = getattr(value, "model_dump", None)
    if (
        callable(model_dump)
        and not inspect.iscoroutinefunction(model_dump)
        and not isinstance(model_dump, AsyncMock)
    ):
        return _normalize_audit_value(model_dump())

    to_dict = getattr(value, "to_dict", None)
    if (
        callable(to_dict)
        and not inspect.iscoroutinefunction(to_dict)
        and not isinstance(to_dict, AsyncMock)
    ):
        try:
            return _normalize_audit_value(to_dict())
        except TypeError:
            pass

    return str(value)


def _normalize_audit_payload(
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Normalize top-level audit payload before persisting.
    写入前规范化顶层审计载荷。
    """
    if payload is None:
        return None

    normalized = _normalize_audit_value(payload)
    if isinstance(normalized, dict):
        return normalized
    return {"value": normalized}


__all__ = [
    "_normalize_audit_payload",
    "_normalize_operator_type",
    "resolve_action_level",
]
