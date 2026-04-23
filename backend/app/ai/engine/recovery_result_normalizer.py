"""Recovery result normalization helpers extracted from RecoveryManager."""

from __future__ import annotations

import json
from typing import Any

from app.core.i18n import _

from .types import IntentPlan

_PAGE_WORKFLOW_GOAL_ALIASES = {
    "page_workflow": "",
    "page_read": "page_summary",
    "page_summary": "page_summary",
    "page_screenshot": "page_screenshot",
    "page_navigation": "navigation",
    "page_search": "search",
    "page_pagination": "pagination",
    "page_row_detail": "row_detail",
    "page_form_read": "form_read",
    "page_form_write": "form_write",
    "page_editor_read": "editor_read",
    "page_editor_write": "editor_write",
}


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
    def _normalize_page_table_result(
        value: dict[str, Any],
        *,
        max_length: int,
    ) -> str | None:
        raw_rows = value.get("rows")
        has_table_shape = isinstance(raw_rows, list) and (
            isinstance(value.get("columns"), list)
            or "table_locator" in value
            or "total_rows" in value
        )
        if not has_table_shape:
            return None

        columns = [
            str(item).strip()
            for item in list(value.get("columns") or [])
            if str(item).strip()
        ][:4]
        row_previews: list[str] = []
        priority_tokens = (
            "title",
            "标题",
            "name",
            "名称",
            "subject",
            "主题",
            "time",
            "时间",
            "date",
            "日期",
            "created",
            "updated",
        )

        for row in raw_rows[:3]:
            if not isinstance(row, dict):
                continue
            preview_parts: list[str] = []
            used_keys: set[str] = set()
            for token in priority_tokens:
                for key, item_value in row.items():
                    key_text = str(key).strip()
                    if not key_text or key_text in used_keys:
                        continue
                    lowered_key = key_text.lower()
                    if token.lower() not in lowered_key and token not in key_text:
                        continue
                    value_text = RecoveryResultNormalizer._normalize_scalar_preview(
                        item_value,
                        max_length=60,
                    )
                    if not value_text:
                        continue
                    preview_parts.append(f"{key_text}={value_text}")
                    used_keys.add(key_text)
                    if len(preview_parts) >= 3:
                        break
                if len(preview_parts) >= 3:
                    break
            if len(preview_parts) < 2:
                for key, item_value in row.items():
                    key_text = str(key).strip()
                    if not key_text or key_text in used_keys:
                        continue
                    value_text = RecoveryResultNormalizer._normalize_scalar_preview(
                        item_value,
                        max_length=60,
                    )
                    if not value_text:
                        continue
                    preview_parts.append(f"{key_text}={value_text}")
                    used_keys.add(key_text)
                    if len(preview_parts) >= 3:
                        break
            if preview_parts:
                row_previews.append("，".join(preview_parts))

        total_rows = value.get("total_rows")
        parts: list[str] = []
        if columns:
            parts.append(_("表格列：{columns}").format(columns="、".join(columns)))
        if row_previews:
            parts.append(_("前几条：{rows}").format(rows="；".join(row_previews)))
        if isinstance(total_rows, int):
            if total_rows <= 0:
                parts.append(_("表格当前没有数据"))
            else:
                parts.append(_("共 {count} 条").format(count=total_rows))

        if not parts:
            return None
        return RecoveryResultNormalizer._truncate_preview(
            "；".join(parts),
            max_length=max_length,
            ensure_sentence=True,
        )

    @staticmethod
    def _normalize_page_region_result(
        value: dict[str, Any],
        *,
        max_length: int,
    ) -> str | None:
        raw_items = value.get("items")
        item_previews: list[str] = []
        if isinstance(raw_items, list):
            for item in raw_items[:3]:
                if not isinstance(item, dict):
                    continue
                label = RecoveryResultNormalizer._normalize_scalar_preview(
                    item.get("label"),
                    max_length=40,
                )
                item_value = RecoveryResultNormalizer._normalize_scalar_preview(
                    item.get("value"),
                    max_length=80,
                )
                if label and item_value:
                    item_previews.append(f"{label}={item_value}")
                elif label:
                    item_previews.append(label)
                elif item_value:
                    item_previews.append(item_value)

        text = RecoveryResultNormalizer._normalize_scalar_preview(
            value.get("text"),
            max_length=min(max_length, 180),
        )
        title = RecoveryResultNormalizer._normalize_scalar_preview(
            value.get("title"),
            max_length=60,
        )
        has_region_shape = bool(
            "region_locator" in value or text or title or item_previews
        )
        if not has_region_shape:
            return None

        detail = text or "；".join(item_previews)
        if title and detail:
            return RecoveryResultNormalizer._truncate_preview(
                _("{title}：{detail}").format(title=title, detail=detail),
                max_length=max_length,
                ensure_sentence=True,
            )
        if detail:
            return RecoveryResultNormalizer._truncate_preview(
                detail,
                max_length=max_length,
                ensure_sentence=True,
            )
        return RecoveryResultNormalizer._truncate_preview(
            title or "",
            max_length=max_length,
            ensure_sentence=True,
        )

    @staticmethod
    def _normalize_page_snapshot_result(
        value: dict[str, Any],
        *,
        max_length: int,
    ) -> str | None:
        raw_nodes = value.get("nodes")
        raw_surface_stack = value.get("surface_stack")
        active_form_summary = (
            value.get("active_form_summary")
            if isinstance(value.get("active_form_summary"), dict)
            else None
        )
        has_snapshot_shape = (
            any(
                key in value
                for key in (
                    "ui_epoch",
                    "active_surface_id",
                    "interactables_count",
                )
            )
            or isinstance(raw_nodes, list)
            or isinstance(raw_surface_stack, list)
        )
        if not has_snapshot_shape:
            return None

        parts: list[str] = []

        surface_title = RecoveryResultNormalizer._resolve_page_snapshot_surface_title(
            value,
            raw_nodes=raw_nodes,
            raw_surface_stack=raw_surface_stack,
        )
        if surface_title:
            parts.append(_("当前焦点：{surface}").format(surface=surface_title))

        node_summaries: list[str] = []
        seen_summaries: set[str] = set()
        if isinstance(raw_nodes, list):
            for node in raw_nodes:
                if not isinstance(node, dict):
                    continue
                summary = (
                    RecoveryResultNormalizer._normalize_page_snapshot_node_summary(
                        node,
                        max_length=50,
                    )
                )
                if not summary:
                    continue
                normalized_summary = (
                    RecoveryResultNormalizer._normalize_comparison_text(summary)
                )
                if len(normalized_summary) < 2 or normalized_summary in seen_summaries:
                    continue
                seen_summaries.add(normalized_summary)
                node_summaries.append(summary)
                if len(node_summaries) >= 4:
                    break
        if node_summaries:
            parts.append(_("页面要点：{items}").format(items="；".join(node_summaries)))

        interactables_count = value.get("interactables_count")
        if isinstance(interactables_count, int) and interactables_count > 0:
            parts.append(_("约 {count} 个可交互元素").format(count=interactables_count))

        if active_form_summary:
            normalized_form = (
                RecoveryResultNormalizer._normalize_page_form_state_result(
                    active_form_summary,
                    max_length=min(max_length, 180),
                )
            )
            if normalized_form:
                parts.append(normalized_form)

        if not parts:
            return None
        return RecoveryResultNormalizer._truncate_preview(
            "；".join(parts),
            max_length=max_length,
            ensure_sentence=True,
        )

    @staticmethod
    def _normalize_page_snapshot_node_summary(
        node: dict[str, Any],
        *,
        max_length: int,
    ) -> str | None:
        if not isinstance(node, dict):
            return None
        return RecoveryResultNormalizer._normalize_scalar_preview(
            node.get("summary")
            or node.get("title")
            or node.get("label")
            or node.get("text")
            or node.get("content"),
            max_length=max_length,
        )

    @staticmethod
    def _page_snapshot_surface_label(surface: dict[str, Any]) -> str:
        if not isinstance(surface, dict):
            return ""
        title = RecoveryResultNormalizer._normalize_scalar_preview(
            surface.get("title"),
            max_length=60,
        )
        kind = RecoveryResultNormalizer._normalize_scalar_preview(
            surface.get("kind"),
            max_length=24,
        )
        if title:
            if kind and kind not in {"page", "surface"}:
                return _("{title}（{kind}）").format(title=title, kind=kind)
            return title
        return kind or ""

    @staticmethod
    def _resolve_page_snapshot_surface_title(
        value: dict[str, Any],
        *,
        raw_nodes: Any,
        raw_surface_stack: Any,
    ) -> str:
        normalized_surface_stack: list[dict[str, Any]] = []
        surface_by_id: dict[str, dict[str, Any]] = {}
        stack_order: dict[str, int] = {}

        if isinstance(raw_surface_stack, list):
            for index, item in enumerate(raw_surface_stack):
                if not isinstance(item, dict):
                    continue
                normalized_item = {
                    "surface_id": RecoveryResultNormalizer._normalize_scalar_preview(
                        item.get("surface_id"),
                        max_length=128,
                    ),
                    "title": item.get("title"),
                    "kind": item.get("kind"),
                }
                normalized_surface_stack.append(normalized_item)
                surface_id = normalized_item["surface_id"]
                if surface_id and surface_id not in surface_by_id:
                    surface_by_id[surface_id] = normalized_item
                    stack_order[surface_id] = index

        active_surface_id = RecoveryResultNormalizer._normalize_scalar_preview(
            value.get("active_surface_id"),
            max_length=128,
        )

        node_surface_scores: dict[str, int] = {}
        node_surface_first_seen: dict[str, int] = {}
        if isinstance(raw_nodes, list):
            for index, node in enumerate(raw_nodes):
                if not isinstance(node, dict):
                    continue
                surface_id = RecoveryResultNormalizer._normalize_scalar_preview(
                    node.get("surface_id"),
                    max_length=128,
                )
                if not surface_id:
                    continue
                summary = (
                    RecoveryResultNormalizer._normalize_page_snapshot_node_summary(
                        node,
                        max_length=50,
                    )
                )
                node_surface_scores[surface_id] = node_surface_scores.get(
                    surface_id, 0
                ) + (2 if summary else 1)
                node_surface_first_seen.setdefault(surface_id, index)

        dominant_surface_id = ""
        if node_surface_scores:
            dominant_surface_id = max(
                node_surface_scores,
                key=lambda surface_id: (
                    node_surface_scores[surface_id],
                    1 if surface_id == active_surface_id else 0,
                    stack_order.get(surface_id, -1),
                    -node_surface_first_seen.get(surface_id, 0),
                ),
            )

        for surface_id in (dominant_surface_id, active_surface_id):
            if not surface_id:
                continue
            surface = surface_by_id.get(surface_id)
            if surface is None:
                continue
            label = RecoveryResultNormalizer._page_snapshot_surface_label(surface)
            if label:
                return label

        for item in reversed(normalized_surface_stack):
            label = RecoveryResultNormalizer._page_snapshot_surface_label(item)
            if label:
                return label

        return active_surface_id or dominant_surface_id or ""

    @staticmethod
    def _normalize_page_interactables_result(
        value: dict[str, Any],
        *,
        max_length: int,
    ) -> str | None:
        raw_items = value.get("items")
        if not isinstance(raw_items, list):
            return None

        item_previews: list[str] = []
        seen_summaries: set[str] = set()
        for item in raw_items[:4]:
            if not isinstance(item, dict):
                continue
            label = RecoveryResultNormalizer._normalize_scalar_preview(
                item.get("label"),
                max_length=60,
            )
            kind = RecoveryResultNormalizer._normalize_scalar_preview(
                item.get("kind"),
                max_length=32,
            )
            locator = RecoveryResultNormalizer._normalize_scalar_preview(
                item.get("locator"),
                max_length=80,
            )
            summary = label or locator or kind
            if label and kind and kind.lower() not in label.lower():
                summary = _("{label}（{kind}）").format(label=label, kind=kind)
            if not summary:
                continue
            normalized_summary = RecoveryResultNormalizer._normalize_comparison_text(
                summary
            )
            if len(normalized_summary) < 2 or normalized_summary in seen_summaries:
                continue
            seen_summaries.add(normalized_summary)
            item_previews.append(summary)

        surface_id = RecoveryResultNormalizer._normalize_scalar_preview(
            value.get("surface_id"),
            max_length=60,
        )
        count = value.get("count")
        if not item_previews and not surface_id and not isinstance(count, int):
            return None

        parts: list[str] = []
        if item_previews:
            parts.append(_("页面要点：{items}").format(items="；".join(item_previews)))
        if isinstance(count, int) and count > 0:
            parts.append(_("约 {count} 个可交互元素").format(count=count))
        if not parts and surface_id:
            parts.append(_("当前页面：{surface}").format(surface=surface_id))
        if not parts:
            return None
        return RecoveryResultNormalizer._truncate_preview(
            "；".join(parts),
            max_length=max_length,
            ensure_sentence=True,
        )

    @staticmethod
    def _normalize_page_form_state_result(
        value: dict[str, Any],
        *,
        max_length: int,
    ) -> str | None:
        raw_fields = value.get("fields")
        remaining_required_fields = [
            str(item).strip()
            for item in list(value.get("remaining_required_fields") or [])
            if str(item).strip()
        ][:4]
        has_form_shape = isinstance(raw_fields, list) or any(
            key in value
            for key in (
                "entity_name",
                "form_session_id",
                "stage",
                "can_submit",
                "remaining_required_fields",
            )
        )
        if not has_form_shape:
            return None

        field_previews: list[str] = []
        if isinstance(raw_fields, list):
            for field in raw_fields[:3]:
                if not isinstance(field, dict):
                    continue
                label = RecoveryResultNormalizer._normalize_scalar_preview(
                    field.get("label") or field.get("name"),
                    max_length=40,
                )
                value_text = RecoveryResultNormalizer._normalize_scalar_preview(
                    field.get("value"),
                    max_length=60,
                )
                if label and value_text:
                    field_previews.append(f"{label}={value_text}")
                elif label:
                    field_previews.append(label)

        parts: list[str] = []
        if field_previews:
            parts.append(
                _("当前字段：{fields}").format(fields="；".join(field_previews))
            )
        if remaining_required_fields:
            parts.append(
                _("待填字段：{fields}").format(
                    fields="、".join(remaining_required_fields)
                )
            )
        if value.get("can_submit") is True:
            parts.append(_("当前表单可以提交"))
        stage = RecoveryResultNormalizer._normalize_scalar_preview(
            value.get("stage"),
            max_length=40,
        )
        if stage:
            parts.append(_("表单阶段：{stage}").format(stage=stage))

        if not parts:
            return None
        entity_name = RecoveryResultNormalizer._normalize_scalar_preview(
            value.get("entity_name"),
            max_length=40,
        )
        preview = "；".join(parts)
        if entity_name:
            preview = _("{entity}表单：{preview}").format(
                entity=entity_name,
                preview=preview,
            )
        return RecoveryResultNormalizer._truncate_preview(
            preview,
            max_length=max_length,
            ensure_sentence=True,
        )

    @staticmethod
    def _normalize_structured_cached_result(
        value: Any,
        *,
        max_length: int = 500,
    ) -> str | None:
        if isinstance(value, dict):
            items = value.get("items")
            if isinstance(items, list):
                interactables_normalized = (
                    RecoveryResultNormalizer._normalize_page_interactables_result(
                        value,
                        max_length=max_length,
                    )
                )
                if interactables_normalized:
                    return interactables_normalized

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

            for normalizer in (
                RecoveryResultNormalizer._normalize_page_snapshot_result,
                RecoveryResultNormalizer._normalize_page_table_result,
                RecoveryResultNormalizer._normalize_page_region_result,
                RecoveryResultNormalizer._normalize_page_interactables_result,
                RecoveryResultNormalizer._normalize_page_form_state_result,
            ):
                normalized_page_result = normalizer(
                    value,
                    max_length=max_length,
                )
                if normalized_page_result:
                    return normalized_page_result

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
    def _intent_page_workflow_goal(intent: IntentPlan) -> str | None:
        if str(intent.family or "").strip().lower() != "page_ops":
            return None
        metadata = dict(intent.metadata or {})
        workflow_goal = str(metadata.get("page_workflow_goal") or "").strip().lower()
        if workflow_goal:
            return _PAGE_WORKFLOW_GOAL_ALIASES.get(workflow_goal, workflow_goal) or None
        intent_kind = str(intent.kind or "").strip().lower()
        return _PAGE_WORKFLOW_GOAL_ALIASES.get(intent_kind) or None

    @classmethod
    def _uses_generic_page_workflow_machine_label(
        cls,
        *,
        intent: IntentPlan,
        label: str | None,
    ) -> bool:
        normalized = str(label or "").strip()
        if not normalized:
            return False
        lowered = normalized.lower()
        if not (normalized.isascii() and ("_" in normalized or lowered == normalized)):
            return False
        workflow_goal = cls._intent_page_workflow_goal(intent)
        if not workflow_goal:
            return False
        candidates = {
            str(intent.kind or "").strip().lower(),
            workflow_goal,
            "page_workflow",
        }
        if workflow_goal == "page_summary":
            candidates.add("page_read")
        return lowered in {item for item in candidates if item}

    @staticmethod
    def _partial_output_label(intent: IntentPlan) -> str:
        label = str(intent.user_visible_label or "").strip()
        if RecoveryResultNormalizer._uses_generic_page_workflow_machine_label(
            intent=intent,
            label=label,
        ):
            return _("这部分")
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
    def _cache_intent_result(intent: IntentPlan, value: Any) -> None:
        normalized = RecoveryResultNormalizer._normalize_cached_result(value)
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
    ) -> str | None:
        if intent_results and intent.intent_id in intent_results:
            normalized = RecoveryResultNormalizer._normalize_cached_result(
                intent_results.get(intent.intent_id)
            )
            if normalized:
                return normalized
        normalized = RecoveryResultNormalizer._normalize_cached_result(
            intent.cached_result
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
                metadata.get(key)
            )
            if normalized:
                return normalized
        return None


__all__ = ["RecoveryResultNormalizer"]
