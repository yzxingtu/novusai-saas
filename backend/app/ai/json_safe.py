"""
JSON-safe runtime normalization helpers.

Keep AI runtime payloads serializable across SSE, persistence, and diagnostics.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from unittest.mock import Mock
from uuid import UUID


def normalize_json_safe(value: Any) -> Any:
    """Recursively convert runtime objects into JSON-safe primitives."""

    if value is None or isinstance(value, (bool, float, int, str)):
        return value
    if isinstance(value, Mock):
        return str(value)
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, Enum):
        return normalize_json_safe(value.value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if is_dataclass(value) and not isinstance(value, type):
        return normalize_json_safe(asdict(value))

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return normalize_json_safe(model_dump(mode="python"))
        except TypeError:
            return normalize_json_safe(model_dump())

    dict_method = getattr(value, "dict", None)
    if callable(dict_method):
        return normalize_json_safe(dict_method())

    if isinstance(value, dict):
        return {str(key): normalize_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [normalize_json_safe(item) for item in value]
    if hasattr(value, "__dict__"):
        return {
            str(key): normalize_json_safe(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def normalize_json_safe_dict(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    payload = normalize_json_safe(raw)
    return payload if isinstance(payload, dict) else None


__all__ = ["normalize_json_safe", "normalize_json_safe_dict"]
