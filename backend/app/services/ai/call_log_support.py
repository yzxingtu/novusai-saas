"""
Call log helper utilities for normalization and sanitization.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder

from app.core.logging import LogManager
from app.enums.ai import CallTypeEnum

logger = LogManager.get_logger("ai.call_log")


class CallLogSupport:
    RESPONSE_TRUNCATE_THRESHOLD = 10 * 1024
    TRUNCATED_MARKER = "...truncated"
    MAX_LATENCY_MS = 2_147_483_647

    @staticmethod
    def _make_json_safe(value: Any) -> Any:
        return jsonable_encoder(
            value,
            custom_encoder={Decimal: lambda raw: str(raw)},
        )

    @staticmethod
    def _normalize_optional_fk_id(value: Any) -> int | None:
        if value is None:
            return None
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return None
        return normalized if normalized > 0 else None

    @classmethod
    def _sanitize_request(cls, request_data: dict) -> dict:
        if not request_data:
            return request_data

        sanitized = request_data.copy()

        if "api_key" in sanitized:
            api_key = str(sanitized["api_key"])
            if len(api_key) > 8:
                sanitized["api_key"] = f"{api_key[:4]}...{api_key[-4:]}"

        sensitive_fields = ["password", "token", "secret", "authorization"]
        for field in sensitive_fields:
            if field in sanitized:
                value = str(sanitized[field])
                if len(value) > 8:
                    sanitized[field] = f"{value[:4]}...{value[-4:]}"

        return cls._make_json_safe(sanitized)

    @classmethod
    def _truncate_response(cls, response_data: Any) -> Any:
        if not response_data:
            return response_data

        response_str = json.dumps(response_data, ensure_ascii=False, default=str)

        if len(response_str.encode("utf-8")) > cls.RESPONSE_TRUNCATE_THRESHOLD:
            return {
                "truncated": True,
                "size": len(response_str),
                "preview": response_str[:1024] + cls.TRUNCATED_MARKER,
            }

        return cls._make_json_safe(response_data)

    @classmethod
    def _generate_request_hash(
        cls,
        model_id: int,
        messages: list,
        temperature: float,
        tools: list | None,
        tool_choice: str | None = None,
    ) -> str:
        params = {
            "model_id": model_id,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": tool_choice,
        }

        params_str = json.dumps(
            cls._make_json_safe(params),
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(params_str.encode()).hexdigest()

    @classmethod
    def _normalize_latency_ms(cls, latency_ms: Any) -> int | None:
        if latency_ms is None:
            return None

        try:
            value = int(latency_ms)
        except (TypeError, ValueError):
            logger.warning("Invalid AI call latency discarded: raw={}", latency_ms)
            return None

        if value < 0:
            logger.warning("Negative AI call latency discarded: raw={}", value)
            return None

        if value > cls.MAX_LATENCY_MS:
            logger.warning(
                "Overflow AI call latency discarded: raw={} max={}",
                value,
                cls.MAX_LATENCY_MS,
            )
            return None

        return value

    @staticmethod
    def _to_non_empty_str(value: Any) -> str | None:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _normalize_bool(value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
        return None

    @classmethod
    def _normalize_turn_record_payload(cls, turn_record: Any) -> dict[str, Any] | None:
        if turn_record is None:
            return None
        if isinstance(turn_record, dict):
            return dict(turn_record)
        if is_dataclass(turn_record) and not isinstance(turn_record, type):
            try:
                payload = asdict(turn_record)
            except Exception:
                payload = None
            if isinstance(payload, dict):
                return payload
            return None
        if hasattr(turn_record, "__dict__"):
            return {
                str(key): value
                for key, value in vars(turn_record).items()
                if not str(key).startswith("_")
            }
        return None

    @classmethod
    def _normalize_context_sources(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized_sources: list[dict[str, Any]] = []
        for raw in value:
            if isinstance(raw, dict):
                source = dict(raw)
            elif hasattr(raw, "__dict__"):
                source = {
                    str(key): item
                    for key, item in vars(raw).items()
                    if not str(key).startswith("_")
                }
            else:
                continue

            metadata = source.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            normalized_sources.append(
                {
                    "kind": str(source.get("kind") or "").strip(),
                    "name": str(source.get("name") or "").strip(),
                    "active": bool(source.get("active", True)),
                    "metadata": dict(metadata),
                }
            )
        return normalized_sources

    @classmethod
    def _normalize_fallback_history(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        normalized_history: list[dict[str, Any]] = []
        for raw in value:
            if isinstance(raw, dict):
                item = dict(raw)
            elif is_dataclass(raw) and not isinstance(raw, type):
                try:
                    payload = asdict(raw)
                except Exception:
                    payload = None
                if not isinstance(payload, dict):
                    continue
                item = payload
            elif hasattr(raw, "__dict__"):
                item = {
                    str(key): item_value
                    for key, item_value in vars(raw).items()
                    if not str(key).startswith("_")
                }
            else:
                continue

            from_protocol = cls._to_non_empty_str(item.get("from_protocol"))
            to_protocol = cls._to_non_empty_str(item.get("to_protocol"))
            reason = cls._to_non_empty_str(item.get("reason"))
            metadata = item.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}

            if not (from_protocol or to_protocol or reason):
                continue

            normalized_history.append(
                {
                    "from_protocol": from_protocol,
                    "to_protocol": to_protocol,
                    "reason": reason,
                    "recovered": bool(item.get("recovered", False)),
                    "metadata": dict(metadata),
                }
            )
        return normalized_history

    @classmethod
    def _pick_first_bool(cls, values: list[Any]) -> bool | None:
        for raw in values:
            parsed = cls._normalize_bool(raw)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _normalize_trace_for_call_log(
        explicit_trace_id: str | None,
        *,
        use_context_var: bool,
    ) -> str | None:
        tid: str | None = None
        if explicit_trace_id is not None and str(explicit_trace_id).strip():
            tid = str(explicit_trace_id).strip()
        elif use_context_var:
            from app.middleware.trace import trace_id_var

            raw = trace_id_var.get()
            tid = str(raw).strip() if raw else None
        if not tid:
            return None
        return tid[:64] if len(tid) > 64 else tid

    @staticmethod
    def _normalize_tool_call_id_for_call_log(tool_call_id: str | None) -> str | None:
        if not tool_call_id or not str(tool_call_id).strip():
            return None
        s = str(tool_call_id).strip()
        return s[:128] if len(s) > 128 else s

    @staticmethod
    def _normalize_call_type_for_call_log(call_type: str | None) -> str:
        text = str(call_type or "").strip()
        if text in CallTypeEnum.values():
            return text
        return CallTypeEnum.MAIN_CHAT.value


__all__ = ["CallLogSupport"]
