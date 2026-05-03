"""Recovery result normalization helpers extracted from RecoveryManager."""

from __future__ import annotations

import json
from typing import Any

from app.core.i18n import _

from .types import IntentPlan


class RecoveryResultNormalizer:
    @staticmethod
    def _truncate_preview(
        text: str,
        *,
        max_length: int,
        ensure_sentence: bool = False,
    ) -> str | None:
        normalized = str(text or "").strip()
        if not normalized:
            return None
        if len(normalized) > max_length:
            normalized = f"{normalized[:max_length].rstrip()}..."
        if ensure_sentence and normalized[-1:] not in {"。", "！", "？", ".", "!", "?"}:
            normalized += "。"
        return normalized

    @staticmethod
    def _normalize_scalar_preview(value: Any, *, max_length: int = 80) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool | int | float):
            return str(value)
        text = str(value).strip()
        if not text:
            return None
        if len(text) > max_length:
            return f"{text[:max_length].rstrip()}..."
        return text

    @staticmethod
    def _normalize_structured_cached_result(
        value: Any,
        *,
        max_length: int = 500,
    ) -> str | None:
        if isinstance(value, dict):
            items = value.get("items")
            if isinstance(items, list):
                normalized_items: list[str] = []
                seen_items: set[str] = set()
                for item in items[:3]:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    if not title and not url:
                        continue
                    label = title or url
                    if title and url:
                        label = f"{title} - {url}"
                    if label in seen_items:
                        continue
                    seen_items.add(label)
                    normalized_items.append(label)
                if normalized_items:
                    return "；".join(normalized_items)

            for nested_key in ("data", "payload"):
                nested_value = value.get(nested_key)
                normalized_nested = RecoveryResultNormalizer._normalize_cached_result(
                    nested_value,
                    max_length=max_length,
                )
                if normalized_nested:
                    return normalized_nested

            city = str(value.get("city") or value.get("location") or "").strip()
            condition = str(
                value.get("condition") or value.get("weather") or ""
            ).strip()
            temperature = str(
                value.get("temperature") or value.get("temp") or ""
            ).strip()
            if city and (condition or temperature):
                parts = [
                    _("{city}现在{condition}").format(
                        city=city,
                        condition=condition,
                    )
                    if condition
                    else city
                ]
                if temperature:
                    parts.append(
                        _("气温约 {temperature}").format(temperature=temperature)
                    )
                return "，".join(part for part in parts if part) + "。"

            for key in (
                "summary",
                "result",
                "message",
                "answer",
                "content",
                "text",
                "output",
                "description",
                "title",
            ):
                candidate = value.get(key)
                if candidate is None:
                    continue
                normalized = RecoveryResultNormalizer._normalize_cached_result(
                    candidate,
                    max_length=max_length,
                )
                if normalized:
                    return normalized
            return None

        if isinstance(value, list):
            items: list[str] = []
            for item in value[:3]:
                normalized = RecoveryResultNormalizer._normalize_cached_result(
                    item,
                    max_length=max_length,
                )
                if normalized and normalized not in items:
                    items.append(normalized)
            if not items:
                return None
            return "；".join(items)

        return None

    @staticmethod
    def _normalize_cached_result(value: Any, *, max_length: int = 500) -> str | None:
        if value is None:
            return None
        structured = RecoveryResultNormalizer._normalize_structured_cached_result(
            value,
            max_length=max_length,
        )
        if structured:
            return structured
        text = str(value).strip()
        if not text:
            return None
        lowered = text.lower()
        if "result(s)" in lowered and "http" not in lowered:
            return None
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = None
            structured = RecoveryResultNormalizer._normalize_structured_cached_result(
                parsed,
                max_length=max_length,
            )
            if structured:
                return structured
            return None
        if len(text) > max_length:
            return f"{text[:max_length].rstrip()}..."
        return text

    @staticmethod
    def _should_prefix_result_with_label(label: str | None) -> bool:
        normalized = str(label or "").strip()
        if not normalized:
            return False
        lowered = normalized.lower()
        if lowered in {
            "direct_reply",
            "time",
            "time_query",
            "weather",
            "weather_query",
            "web_research",
        }:
            return False
        return not (
            normalized.isascii() and ("_" in normalized or lowered == normalized)
        )

    @staticmethod
    def _partial_output_label(intent: IntentPlan) -> str:
        label = str(intent.user_visible_label or "").strip()
        if RecoveryResultNormalizer._should_prefix_result_with_label(label):
            return label
        normalized_kind = str(intent.kind or "").strip().lower()
        normalized_family = str(intent.family or "").strip().lower()
        if normalized_kind == "web_research" or normalized_family == "web_research":
            return _("这些来源")
        if normalized_kind == "weather_query" or normalized_family == "weather":
            return _("天气")
        if normalized_kind == "time_query" or normalized_family == "time_ops":
            return _("时间")
        return _("这部分")

    @staticmethod
    def _cache_intent_result(
        intent: IntentPlan,
        value: Any,
        *,
        max_length: int = 500,
    ) -> None:
        normalized = RecoveryResultNormalizer._normalize_cached_result(
            value,
            max_length=max_length,
        )
        if not normalized:
            return
        intent.cached_result = normalized
        intent.metadata = dict(intent.metadata or {})
        intent.metadata["cached_result"] = normalized

    @staticmethod
    def _cache_partial_intent_result(intent: IntentPlan, value: Any) -> None:
        normalized = RecoveryResultNormalizer._normalize_cached_result(value)
        if not normalized:
            return
        intent.metadata = dict(intent.metadata or {})
        intent.metadata["partial_result"] = normalized

    @staticmethod
    def _normalize_comparison_text(text: str) -> str:
        return "".join(ch for ch in str(text or "").casefold() if ch.isalnum())

    @staticmethod
    def _intent_cached_result(
        intent: IntentPlan,
        *,
        intent_results: dict[str, str] | None = None,
        max_length: int = 500,
    ) -> str | None:
        if intent_results and intent.intent_id in intent_results:
            normalized = RecoveryResultNormalizer._normalize_cached_result(
                intent_results.get(intent.intent_id),
                max_length=max_length,
            )
            if normalized:
                return normalized
        normalized = RecoveryResultNormalizer._normalize_cached_result(
            intent.cached_result,
            max_length=max_length,
        )
        if normalized:
            return normalized
        metadata = dict(intent.metadata or {})
        for key in (
            "cached_result",
            "intent_result",
            "result_summary",
            "partial_result",
        ):
            normalized = RecoveryResultNormalizer._normalize_cached_result(
                metadata.get(key),
                max_length=max_length,
            )
            if normalized:
                return normalized
        return None


__all__ = ["RecoveryResultNormalizer"]
