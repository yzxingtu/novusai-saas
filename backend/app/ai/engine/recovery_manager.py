"""Intent-scoped recovery and partial-exit helpers."""

from __future__ import annotations

import json
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _

from .types import ExecutionBudget, IntentPlan, ProviderFailureKind, RecoveryDecision


class RecoveryManager:
    _BUDGET_EXIT_REASONS: frozenset[str] = frozenset(
        {
            "prompt_budget_exceeded",
            "completion_budget_exceeded",
            "tool_round_budget_exceeded",
            "elapsed_budget_exceeded",
            "tool_result_budget_exceeded",
            "candidate_tool_budget_exceeded",
        }
    )
    _RETRYABLE_FAILURE_KINDS: frozenset[ProviderFailureKind] = frozenset(
        {"tool_timeout", "tool_execution_error", "provider_timeout", "provider_rate_limit"}
    )
    _TERMINAL_FAILURE_KINDS: frozenset[ProviderFailureKind] = frozenset(
        {
            "provider_unavailable",
            "provider_http_5xx",
            "provider_bad_response",
            "server_interrupt",
        }
    )

    @staticmethod
    def is_budget_exit_reason(reason: str) -> bool:
        return reason in RecoveryManager._BUDGET_EXIT_REASONS

    @staticmethod
    def is_retryable_failure_kind(kind: ProviderFailureKind) -> bool:
        return kind in RecoveryManager._RETRYABLE_FAILURE_KINDS

    @staticmethod
    def is_terminal_failure_kind(kind: ProviderFailureKind) -> bool:
        return kind == "budget_exit" or kind in RecoveryManager._TERMINAL_FAILURE_KINDS

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

            city = str(value.get("city") or value.get("location") or "").strip()
            condition = str(
                value.get("condition") or value.get("weather") or ""
            ).strip()
            temperature = str(
                value.get("temperature") or value.get("temp") or ""
            ).strip()
            if city and (condition or temperature):
                parts = [f"{city}现在{condition}" if condition else city]
                if temperature:
                    parts.append(f"气温约 {temperature}")
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
                normalized = RecoveryManager._normalize_cached_result(
                    candidate,
                    max_length=max_length,
                )
                if normalized:
                    return normalized
            return None

        if isinstance(value, list):
            items: list[str] = []
            for item in value[:3]:
                normalized = RecoveryManager._normalize_cached_result(
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
        structured = RecoveryManager._normalize_structured_cached_result(
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
            structured = RecoveryManager._normalize_structured_cached_result(
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
            "page_read",
            "page_summary",
        }:
            return False
        return not (
            normalized.isascii() and ("_" in normalized or lowered == normalized)
        )

    @staticmethod
    def _partial_output_label(intent: IntentPlan) -> str:
        label = str(intent.user_visible_label or "").strip()
        if RecoveryManager._should_prefix_result_with_label(label):
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
        normalized = RecoveryManager._normalize_cached_result(value)
        if not normalized:
            return
        intent.cached_result = normalized
        intent.metadata = dict(intent.metadata or {})
        intent.metadata["cached_result"] = normalized

    @staticmethod
    def _cache_partial_intent_result(intent: IntentPlan, value: Any) -> None:
        normalized = RecoveryManager._normalize_cached_result(value)
        if not normalized:
            return
        intent.metadata = dict(intent.metadata or {})
        intent.metadata["partial_result"] = normalized

    @staticmethod
    def _normalize_comparison_text(text: str) -> str:
        return "".join(ch for ch in str(text or "").casefold() if ch.isalnum())

    @staticmethod
    def _extract_fetch_url_user_preview(
        result: ToolResult,
        *,
        max_length: int = 500,
    ) -> str | None:
        summary_payload = (
            dict(result.summary_payload)
            if isinstance(result.summary_payload, dict)
            else {}
        )
        if not summary_payload.get("fetch_url"):
            return None

        title = str(summary_payload.get("title") or "").strip()
        description = str(summary_payload.get("description") or "").strip()
        generic_summary = str(
            summary_payload.get("summary") or result.summary or ""
        ).strip()
        title_has_site_suffix = "|" in title or "_" in title
        normalized_title = RecoveryManager._normalize_comparison_text(title)
        normalized_description = RecoveryManager._normalize_comparison_text(description)
        normalized_summary = RecoveryManager._normalize_comparison_text(generic_summary)
        summary_truncated = generic_summary.endswith(("...", "…"))
        description_truncated = description.endswith(("...", "…"))

        useful_lines: list[str] = []
        for raw_line in str(result.output or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(
                (
                    "Content from ",
                    "Redirected from: ",
                    "Title: ",
                    "Description: ",
                    "Key sections: ",
                )
            ):
                continue
            normalized_line = RecoveryManager._normalize_comparison_text(line)
            if not normalized_line:
                continue
            if normalized_title and normalized_line == normalized_title:
                continue
            if normalized_description and normalized_line == normalized_description:
                continue
            useful_lines.append(line)
            if len(" ".join(useful_lines)) >= max_length:
                break

        if (
            generic_summary
            and normalized_summary != normalized_title
            and not summary_truncated
            and not title_has_site_suffix
        ):
            return RecoveryManager._normalize_cached_result(
                generic_summary,
                max_length=max_length,
            )
        if useful_lines and (
            summary_truncated or description_truncated or title_has_site_suffix
        ):
            preview_parts: list[str] = []
            if description and description not in useful_lines[:2]:
                preview_parts.append(description)
            preview_parts.extend(useful_lines[:2])
            preview = " ".join(part.strip() for part in preview_parts if part.strip())
            normalized_preview = RecoveryManager._normalize_comparison_text(preview)
            if normalized_preview and normalized_preview != normalized_title:
                return RecoveryManager._normalize_cached_result(
                    preview,
                    max_length=max_length,
                )
        if title and description and not title_has_site_suffix:
            return RecoveryManager._normalize_cached_result(
                f"{title} - {description}",
                max_length=max_length,
            )
        if description:
            return RecoveryManager._normalize_cached_result(
                description,
                max_length=max_length,
            )

        preview_parts: list[str] = []
        if description:
            preview_parts.append(description)
        if useful_lines:
            preview_parts.extend(useful_lines[:2])

        preview = " ".join(part.strip() for part in preview_parts if part.strip())
        normalized_preview = RecoveryManager._normalize_comparison_text(preview)
        if normalized_preview and normalized_preview != normalized_title:
            return RecoveryManager._normalize_cached_result(
                preview,
                max_length=max_length,
            )
        if title:
            return RecoveryManager._normalize_cached_result(title, max_length=max_length)
        return None

    @staticmethod
    def _budgeted_web_research_response_candidates(
        tool_results: list[ToolResult] | None = None,
    ) -> list[str]:
        candidates: list[str] = []
        for result in tool_results or []:
            if not result.success or str(result.name or "").strip() != "fetch_url":
                continue
            payload = (
                dict(result.summary_payload)
                if isinstance(result.summary_payload, dict)
                else {}
            )
            raw_title = str(payload.get("title") or "").strip()
            description = str(payload.get("description") or "").strip()
            for candidate in (
                payload.get("summary"),
                f"{raw_title} - {description}" if raw_title and description else None,
                RecoveryManager._extract_fetch_url_user_preview(result),
                description,
                result.summary,
                raw_title,
            ):
                normalized = RecoveryManager._normalize_cached_result(candidate)
                if normalized and normalized not in candidates:
                    candidates.append(normalized)
        return candidates

    @staticmethod
    def should_replace_budgeted_web_research_response(
        *,
        response_text: str,
        tool_results: list[ToolResult] | None = None,
    ) -> bool:
        raw_response = str(response_text or "").strip()
        if not raw_response:
            return True

        lowered_response = raw_response.casefold()
        if lowered_response.startswith(("content from ", "title: ", "description: ")):
            return True

        normalized_response = RecoveryManager._normalize_comparison_text(raw_response)
        if not normalized_response:
            return True

        for candidate in RecoveryManager._budgeted_web_research_response_candidates(
            tool_results
        ):
            normalized_candidate = RecoveryManager._normalize_comparison_text(candidate)
            if normalized_candidate and normalized_response == normalized_candidate:
                return True
        return False

    @staticmethod
    def _intent_result_from_tool_results(
        intent: IntentPlan,
        tool_results: list[ToolResult] | None = None,
    ) -> str | None:
        if not tool_results:
            return None
        candidate_tool_names: list[str] = []
        prioritized_tool_names = list(intent.completed_by_tool_names or [])
        if not prioritized_tool_names:
            prioritized_tool_names = list(intent.completion_signals or []) + list(
                intent.allowed_tool_names or []
            )
        for tool_name in prioritized_tool_names:
            normalized_name = str(tool_name or "").strip()
            if normalized_name and normalized_name not in candidate_tool_names:
                candidate_tool_names.append(normalized_name)
        if (
            not intent.completed_by_tool_names
            and str(intent.family or "").strip() == "web_research"
            and "web_search" not in candidate_tool_names
        ):
            candidate_tool_names.append("web_search")
        if not candidate_tool_names:
            return None
        normalized_results: list[str] = []
        for name in candidate_tool_names:
            for result in tool_results:
                if not result.success or result.name != name:
                    continue
                if (
                    str(intent.family or "").strip() == "web_research"
                    and str(result.name or "").strip() == "fetch_url"
                ):
                    preview = RecoveryManager._extract_fetch_url_user_preview(result)
                    if preview:
                        if preview not in normalized_results:
                            normalized_results.append(preview)
                        continue
                for candidate in (
                    result.summary_payload,
                    result.summary,
                    result.output or result.error,
                ):
                    normalized = RecoveryManager._normalize_cached_result(candidate)
                    if normalized:
                        if normalized not in normalized_results:
                            normalized_results.append(normalized)
                        break
        if not normalized_results:
            return None
        return "；".join(normalized_results[:2])

    @staticmethod
    def _intent_cached_result(
        intent: IntentPlan,
        *,
        intent_results: dict[str, str] | None = None,
    ) -> str | None:
        if intent_results and intent.intent_id in intent_results:
            normalized = RecoveryManager._normalize_cached_result(
                intent_results.get(intent.intent_id)
            )
            if normalized:
                return normalized
        normalized = RecoveryManager._normalize_cached_result(intent.cached_result)
        if normalized:
            return normalized
        metadata = dict(intent.metadata or {})
        for key in (
            "cached_result",
            "intent_result",
            "result_summary",
            "partial_result",
        ):
            normalized = RecoveryManager._normalize_cached_result(metadata.get(key))
            if normalized:
                return normalized
        return None

    @staticmethod
    def _partial_exit_labels(intents: list[IntentPlan]) -> tuple[list[str], list[str]]:
        completed = [
            intent.user_visible_label
            for intent in intents
            if intent.status == "completed"
        ]
        unfinished = [
            intent.user_visible_label
            for intent in intents
            if intent.status != "completed"
        ]
        return completed, unfinished

    @staticmethod
    def _successful_tool_names(
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
    ) -> list[str]:
        names: list[str] = []
        for result in tool_results or []:
            if result.success and result.name not in names:
                names.append(result.name)
        for message in messages:
            if message.role != "assistant" or not message.tool_calls:
                continue
            for tool_call in message.tool_calls:
                if tool_call.get("success") is not True:
                    continue
                func = tool_call.get("function") or {}
                name = str(func.get("name") or tool_call.get("name") or "").strip()
                if name and name not in names:
                    names.append(name)
        return names

    @staticmethod
    def _tool_attempted(
        messages: list[ChatMessage],
        tool_name: str,
        tool_results: list[ToolResult] | None = None,
    ) -> bool:
        normalized_name = str(tool_name or "").strip()
        if not normalized_name:
            return False
        for result in tool_results or []:
            if str(result.name or "").strip() == normalized_name:
                return True
        for message in messages:
            if message.role != "assistant" or not message.tool_calls:
                continue
            for tool_call in message.tool_calls:
                func = tool_call.get("function") or {}
                name = str(func.get("name") or tool_call.get("name") or "").strip()
                if name == normalized_name:
                    return True
        return False

    @staticmethod
    def _normalized_url_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            url = str(item or "").strip()
            if url and url not in normalized:
                normalized.append(url)
        return normalized

    @staticmethod
    def _extract_fetch_url_candidate_urls(
        tool_results: list[ToolResult] | None,
    ) -> list[str]:
        candidate_urls: list[str] = []
        for result in tool_results or []:
            if not result.success or str(result.name or "").strip() != "web_search":
                continue
            payload = result.summary_payload if isinstance(result.summary_payload, dict) else {}
            items = payload.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                if url and url not in candidate_urls:
                    candidate_urls.append(url)
        return candidate_urls

    @staticmethod
    def _sync_fetch_url_candidates(
        intent: IntentPlan,
        tool_results: list[ToolResult] | None = None,
    ) -> None:
        if str(intent.family or "").strip() != "web_research":
            return
        candidate_urls = RecoveryManager._extract_fetch_url_candidate_urls(tool_results)
        if not candidate_urls:
            return
        metadata = dict(intent.metadata or {})
        existing_urls = RecoveryManager._normalized_url_list(
            metadata.get("fetch_url_candidate_urls")
        )
        merged_urls = list(existing_urls)
        for url in candidate_urls:
            if url not in merged_urls:
                merged_urls.append(url)
        metadata["fetch_url_candidate_urls"] = merged_urls
        metadata["fetch_url_attempted_urls"] = RecoveryManager._normalized_url_list(
            metadata.get("fetch_url_attempted_urls")
        )
        metadata["fetch_url_blocked_urls"] = RecoveryManager._normalized_url_list(
            metadata.get("fetch_url_blocked_urls")
        )
        intent.metadata = metadata

    @staticmethod
    def _latest_successful_tool_result(
        tool_name: str,
        tool_results: list[ToolResult] | None = None,
    ) -> ToolResult | None:
        normalized_name = str(tool_name or "").strip()
        if not normalized_name:
            return None
        for result in reversed(tool_results or []):
            if result.success and str(result.name or "").strip() == normalized_name:
                return result
        return None

    @staticmethod
    def _web_search_result_count(tool_results: list[ToolResult] | None = None) -> int | None:
        result = RecoveryManager._latest_successful_tool_result("web_search", tool_results)
        if result is None:
            return None
        payload = result.summary_payload if isinstance(result.summary_payload, dict) else {}
        raw_count = payload.get("result_count")
        try:
            if raw_count is not None:
                return max(0, int(raw_count))
        except (TypeError, ValueError):
            pass
        items = payload.get("items")
        if isinstance(items, list):
            return len(items)
        return None

    @staticmethod
    def _set_auto_fetch_gate_reason(intent: IntentPlan, reason: str) -> None:
        metadata = dict(intent.metadata or {})
        metadata["auto_fetch_gate_reason"] = str(reason or "").strip() or None
        if metadata["auto_fetch_gate_reason"] is None:
            metadata.pop("auto_fetch_gate_reason", None)
        intent.metadata = metadata

    @staticmethod
    def _clear_requires_fetch_url(intent: IntentPlan, *, reason: str) -> None:
        metadata = dict(intent.metadata or {})
        metadata.pop("requires_fetch_url", None)
        metadata["auto_fetch_gate_reason"] = str(reason or "").strip() or None
        intent.metadata = metadata

    @staticmethod
    def _web_research_no_result_output(intent: IntentPlan) -> str:
        label = str(intent.user_visible_label or "").strip()
        if RecoveryManager._should_prefix_result_with_label(label):
            return _("关于{label}，我暂时没有找到可直接核实的搜索结果。").format(
                label=label
            )
        return _("我暂时没有找到可直接核实的搜索结果。")

    @staticmethod
    def _is_completed_web_research_no_result(
        intent: IntentPlan,
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
        successful_tool_names: set[str],
    ) -> bool:
        if str(intent.family or "").strip() != "web_research":
            return False
        if "web_search" not in successful_tool_names:
            return False
        candidate_urls = RecoveryManager._normalized_url_list(
            (intent.metadata or {}).get("fetch_url_candidate_urls")
        )
        if candidate_urls:
            return False
        if RecoveryManager._tool_attempted(
            messages,
            "fetch_url",
            tool_results=tool_results,
        ):
            return False
        result_count = RecoveryManager._web_search_result_count(tool_results)
        if result_count is None:
            return True
        return result_count <= 0

    @staticmethod
    def _force_fetch_url_after_search(
        intent: IntentPlan,
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
        successful_tool_names: set[str],
    ) -> None:
        if str(intent.family or "").strip() != "web_research":
            return

        RecoveryManager._sync_fetch_url_candidates(intent, tool_results)
        metadata = dict(intent.metadata or {})
        candidate_urls = RecoveryManager._normalized_url_list(
            metadata.get("fetch_url_candidate_urls")
        )
        attempted_urls = set(
            RecoveryManager._normalized_url_list(metadata.get("fetch_url_attempted_urls"))
        )
        remaining_candidate_urls = [
            url for url in candidate_urls if url not in attempted_urls
        ]
        web_search_result_count = RecoveryManager._web_search_result_count(tool_results)
        candidate_tool_names = {
            str(name or "").strip()
            for name in (
                list(intent.allowed_tool_names or [])
                + list(intent.preferred_tool_names or [])
                + list(intent.completion_signals or [])
            )
            if str(name or "").strip()
        }
        if "fetch_url" not in candidate_tool_names:
            return
        if "web_search" not in successful_tool_names:
            RecoveryManager._clear_requires_fetch_url(
                intent,
                reason="search_not_successful",
            )
            return
        if web_search_result_count is not None and web_search_result_count <= 0:
            RecoveryManager._clear_requires_fetch_url(
                intent,
                reason="search_no_results",
            )
            return
        if not candidate_urls:
            RecoveryManager._clear_requires_fetch_url(
                intent,
                reason="no_candidate_urls",
            )
            return
        if RecoveryManager._tool_attempted(
            messages,
            "fetch_url",
            tool_results=tool_results,
        ):
            RecoveryManager._clear_requires_fetch_url(
                intent,
                reason="fetch_already_attempted",
            )
            return
        if not remaining_candidate_urls:
            RecoveryManager._clear_requires_fetch_url(
                intent,
                reason="candidate_urls_exhausted",
            )
            return

        intent.allowed_tool_names = ["fetch_url"]
        intent.preferred_tool_names = ["fetch_url"]
        intent.completion_signals = ["fetch_url"]
        intent.metadata["requires_fetch_url"] = True
        intent.metadata["auto_fetch_gate_reason"] = "candidate_urls_ready"

    @staticmethod
    def _pending_consent_payload_from_tool_calls(
        tool_calls: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        for tool_call in tool_calls or []:
            payload = tool_call.get("pending_consent")
            if isinstance(payload, dict) and not payload.get("resolved"):
                return dict(payload)
        return None

    @staticmethod
    def _extract_pending_consent_payload(
        messages: list[ChatMessage],
    ) -> dict[str, Any] | None:
        for message in reversed(messages):
            meta = message.metadata or {}
            payload = meta.get("pending_consent")
            if isinstance(payload, dict) and not payload.get("resolved"):
                return dict(payload)
            payload = RecoveryManager._pending_consent_payload_from_tool_calls(
                message.tool_calls
            )
            if payload:
                return payload
        return None

    @staticmethod
    def pending_consent_payload_from_decision(
        decision: RecoveryDecision | None,
    ) -> dict[str, Any] | None:
        if decision is None:
            return None
        meta = dict(decision.metadata or {})
        payload = meta.get("pending_consent")
        return dict(payload) if isinstance(payload, dict) else None

    @staticmethod
    def ensure_latest_assistant_pending_consent(
        messages: list[ChatMessage],
        payload: dict[str, Any] | None,
    ) -> None:
        if not isinstance(payload, dict) or not payload:
            return
        normalized_payload = dict(payload)
        for message in reversed(messages):
            if message.role != "assistant":
                continue
            metadata = dict(message.metadata or {})
            metadata["pending_consent"] = normalized_payload
            message.metadata = metadata
            return
        messages.append(
            ChatMessage(
                role="assistant",
                content="",
                metadata={"pending_consent": normalized_payload},
            )
        )

    @staticmethod
    def complete_native_search_intents(intents: list[IntentPlan]) -> list[IntentPlan]:
        """Mark pending web_research intents as completed when native search
        (Responses API) produced a visible response, so the orchestrator does not
        treat them as unfinished and trigger an unnecessary recovery retry."""
        updated: list[IntentPlan] = []
        for intent in intents:
            clone = IntentPlan(**intent.to_dict())
            if (
                clone.status == "pending"
                and str(clone.family or "").strip() == "web_research"
                and clone.requires_tools
            ):
                clone.status = "completed"
                clone.completed_by_tool_names = ["native_web_search"]
                clone.metadata = dict(clone.metadata or {})
                clone.metadata["auto_fetch_gate_reason"] = "native_search_completed"
            updated.append(clone)
        return updated

    @staticmethod
    def update_intent_statuses(
        intents: list[IntentPlan],
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
    ) -> list[IntentPlan]:
        successful_tool_names = set(
            RecoveryManager._successful_tool_names(messages, tool_results)
        )
        pending_payload = RecoveryManager._extract_pending_consent_payload(messages)
        pending_consent_assigned = False
        updated: list[IntentPlan] = []
        for intent in intents:
            clone = IntentPlan(**intent.to_dict())
            clone.metadata = dict(clone.metadata or {})
            clone.metadata.pop("pending_consent", None)
            RecoveryManager._force_fetch_url_after_search(
                clone,
                messages=messages,
                tool_results=tool_results,
                successful_tool_names=successful_tool_names,
            )
            completion_signals = set(
                clone.completion_signals or clone.allowed_tool_names
            )
            if clone.family == "none" or not clone.requires_tools:
                clone.status = "completed"
            elif RecoveryManager._is_completed_web_research_no_result(
                clone,
                messages=messages,
                tool_results=tool_results,
                successful_tool_names=successful_tool_names,
            ):
                clone.status = "completed"
                clone.completed_by_tool_names = ["web_search"]
                RecoveryManager._clear_requires_fetch_url(
                    clone,
                    reason="search_no_results_completed",
                )
                RecoveryManager._cache_intent_result(
                    clone,
                    RecoveryManager._web_research_no_result_output(clone),
                )
            elif completion_signals & successful_tool_names:
                clone.status = "completed"
                clone.completed_by_tool_names = sorted(
                    completion_signals & successful_tool_names
                )
            if clone.status == "completed":
                cached_result = None
                if (
                    str(clone.metadata.get("auto_fetch_gate_reason") or "").strip()
                    == "search_no_results_completed"
                ):
                    cached_result = RecoveryManager._intent_cached_result(clone)
                if not cached_result:
                    cached_result = RecoveryManager._intent_result_from_tool_results(
                        clone,
                        tool_results,
                    )
                if not cached_result:
                    cached_result = RecoveryManager._intent_cached_result(clone)
                if cached_result:
                    RecoveryManager._cache_intent_result(clone, cached_result)
            elif clone.status not in {"failed", "skipped"}:
                clone.status = "pending"
                partial_result = RecoveryManager._intent_result_from_tool_results(
                    clone,
                    tool_results,
                )
                if partial_result:
                    RecoveryManager._cache_partial_intent_result(
                        clone,
                        partial_result,
                    )
            if (
                pending_payload
                and not pending_consent_assigned
                and clone.status not in {"completed", "failed", "skipped"}
                and clone.requires_tools
            ):
                clone.status = "awaiting_consent"
                clone.metadata["pending_consent"] = dict(pending_payload)
                pending_consent_assigned = True
            updated.append(clone)
        return updated

    @staticmethod
    def next_unfinished_intents(intents: list[IntentPlan]) -> list[IntentPlan]:
        return [
            intent
            for intent in intents
            if intent.status not in {"completed", "skipped"}
        ]

    @staticmethod
    def _pending_consent_intent(intents: list[IntentPlan]) -> IntentPlan | None:
        for intent in intents:
            if intent.status == "awaiting_consent":
                return intent
        return None

    @staticmethod
    def decide(
        intents: list[IntentPlan],
        *,
        budget: ExecutionBudget | None,
        provider_failure_kind: ProviderFailureKind = "none",
    ) -> RecoveryDecision | None:
        unfinished = RecoveryManager.next_unfinished_intents(intents)
        completed = [
            intent.intent_id for intent in intents if intent.status == "completed"
        ]
        pending_intent = RecoveryManager._pending_consent_intent(intents)
        if pending_intent:
            pending_meta = (pending_intent.metadata or {}).get("pending_consent")
            payload = dict(pending_meta) if isinstance(pending_meta, dict) else None
            metadata: dict[str, Any] = {}
            if payload:
                metadata["pending_consent"] = payload
            return RecoveryDecision(
                action="pause_for_consent",
                target_intent_id=pending_intent.intent_id,
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="awaiting_user_consent",
                provider_failure_kind=provider_failure_kind,
                metadata=metadata,
            )
        budget_exit_reason = (
            budget.first_exceeded_reason() if budget is not None else None
        )
        if budget_exit_reason:
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason=budget_exit_reason,
                provider_failure_kind=(
                    "budget_exit"
                    if provider_failure_kind == "none"
                    else provider_failure_kind
                ),
            )
        if provider_failure_kind == "budget_exit":
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="budget_exit",
                provider_failure_kind=provider_failure_kind,
            )
        if not unfinished and provider_failure_kind == "none":
            return None
        if unfinished:
            target = unfinished[0]
            if (
                provider_failure_kind != "none"
                and not RecoveryManager.is_retryable_failure_kind(provider_failure_kind)
            ):
                return RecoveryDecision(
                    action="return_partial",
                    completed_intent_ids=completed,
                    unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                    reason="terminal_failure",
                    provider_failure_kind=provider_failure_kind,
                )
            retry_count = int(
                (
                    budget.retries_by_intent.get(target.intent_id, 0)
                    if budget is not None
                    else 0
                )
                or 0
            )
            if budget is not None and retry_count >= budget.max_retry_per_intent:
                return RecoveryDecision(
                    action="return_partial",
                    completed_intent_ids=completed,
                    unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                    reason="retry_budget_exhausted",
                    provider_failure_kind=provider_failure_kind,
                )
            return RecoveryDecision(
                action="retry_intent",
                target_intent_id=target.intent_id,
                retry_family=target.family,
                allowed_tool_names=list(target.allowed_tool_names),
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="unfinished_intent_retry",
                provider_failure_kind=provider_failure_kind,
            )
        if provider_failure_kind != "none":
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[],
                reason=(
                    "terminal_failure"
                    if RecoveryManager.is_terminal_failure_kind(provider_failure_kind)
                    else "provider_failure_after_partial_progress"
                ),
                provider_failure_kind=provider_failure_kind,
            )
        return RecoveryDecision(
            action="return_partial",
            completed_intent_ids=completed,
            unfinished_intent_ids=[],
            reason="provider_failure_after_partial_progress",
            provider_failure_kind=provider_failure_kind,
        )

    @staticmethod
    def build_recovery_message(
        *,
        decision: RecoveryDecision,
        intents: list[IntentPlan],
    ) -> ChatMessage:
        completed = [
            intent.user_visible_label
            for intent in intents
            if intent.intent_id in decision.completed_intent_ids
        ]
        unfinished = [
            intent.user_visible_label
            for intent in intents
            if intent.intent_id in decision.unfinished_intent_ids
        ]
        return ChatMessage(
            role="system",
            content=render_prompt_contract(
                "contract_recovery",
                breach_guidance="Only finish the remaining intent(s) listed below.\n",
                unfinished_line=(
                    f"Unfinished requested intents: {', '.join(unfinished)}.\n"
                    if unfinished
                    else ""
                ),
                completed_line=(
                    "Already completed intents with real tool evidence: "
                    f"{', '.join(completed)}.\n"
                    if completed
                    else ""
                ),
                leaked_line=(
                    f"Allowed tools for this recovery: {', '.join(decision.allowed_tool_names)}.\n"
                    if decision.allowed_tool_names
                    else ""
                ),
            ),
        )

    @staticmethod
    def build_missing_args_clarification_message(
        *,
        decision: RecoveryDecision,
        intents: list[IntentPlan],
        missing_args: list[str],
    ) -> ChatMessage:
        completed = [
            intent.user_visible_label
            for intent in intents
            if intent.intent_id in decision.completed_intent_ids
        ]
        unfinished = [
            intent.user_visible_label
            for intent in intents
            if intent.intent_id in decision.unfinished_intent_ids
        ]
        return ChatMessage(
            role="system",
            content=render_prompt_contract(
                "contract_recovery",
                breach_guidance=(
                    "Do not call any tools yet. Ask one short clarification question "
                    "to collect the missing arguments needed for the remaining intent(s).\n"
                ),
                unfinished_line=(
                    f"Unfinished requested intents: {', '.join(unfinished)}.\n"
                    if unfinished
                    else ""
                ),
                completed_line=(
                    "Already completed intents with real tool evidence: "
                    f"{', '.join(completed)}.\n"
                    if completed
                    else ""
                ),
                leaked_line=(
                    f"Missing arguments that must be clarified first: {', '.join(missing_args)}.\n"
                    if missing_args
                    else ""
                ),
            ),
        )

    @staticmethod
    def build_partial_output(
        intents: list[IntentPlan],
        *,
        reason: str,
        provider_failure_kind: ProviderFailureKind = "none",
        intent_results: dict[str, str] | None = None,
    ) -> str:
        completed_results: list[str] = []
        completed_labels: list[str] = []
        unfinished_results: list[str] = []
        unfinished_labels: list[str] = []
        retry_budget_exhausted = reason == "retry_budget_exhausted"
        for intent in intents:
            display_label = RecoveryManager._partial_output_label(intent)
            intent_result = RecoveryManager._intent_cached_result(
                intent,
                intent_results=intent_results,
            )
            if intent.status == "completed":
                if intent_result:
                    if intent_result not in completed_results:
                        completed_results.append(intent_result)
                elif display_label and display_label not in completed_labels:
                    completed_labels.append(display_label)
                continue
            if intent_result:
                result_line = intent_result
                if (
                    RecoveryManager._should_prefix_result_with_label(
                        intent.user_visible_label
                    )
                    and intent.user_visible_label not in result_line
                ):
                    result_line = f"{intent.user_visible_label}：{intent_result}"
                if result_line not in unfinished_results:
                    unfinished_results.append(result_line)
            if display_label and display_label not in unfinished_labels:
                unfinished_labels.append(display_label)

        parts: list[str] = []
        parts.extend(completed_results)
        if completed_labels:
            parts.append(_("我先把已完成部分整理给你：{completed}。").format(completed="、".join(completed_labels)))
        if unfinished_results:
            parts.append(
                _("我先把目前拿到的结果给你：{results}。").format(
                    results="；".join(unfinished_results)
                )
            )

        unfinished_summary = "、".join(unfinished_labels)
        if unfinished_summary:
            if provider_failure_kind == "tool_timeout":
                parts.append(
                    _("{unfinished}暂时超时了，你可以稍后再问。").format(
                        unfinished=unfinished_summary
                    )
                )
            elif (
                provider_failure_kind == "budget_exit"
                or RecoveryManager.is_budget_exit_reason(reason)
                or retry_budget_exhausted
            ):
                parts.append(
                    _("{unfinished}还需要继续核验，我先把目前能确认的内容给你。").format(
                        unfinished=unfinished_summary
                    )
                )
            elif RecoveryManager.is_terminal_failure_kind(provider_failure_kind):
                parts.append(
                    _("{unfinished}被系统中断了，请稍后再试。").format(
                        unfinished=unfinished_summary
                    )
                )
            elif provider_failure_kind != "none":
                parts.append(
                    _("{unfinished}被暂时中断了，请稍后再试。").format(
                        unfinished=unfinished_summary
                    )
                )
            else:
                parts.append(
                    _("{unfinished}还没有完成。如果你愿意，我可以继续。").format(
                        unfinished=unfinished_summary
                    )
                )
        if parts:
            return " ".join(part.strip() for part in parts if part.strip())
        if (
            reason == "budget_exit"
            or provider_failure_kind == "budget_exit"
            or RecoveryManager.is_budget_exit_reason(reason)
            or retry_budget_exhausted
        ):
            return _("这次处理在本轮收口前达到了限制，我先把目前能确认的内容给你。")
        if RecoveryManager.is_terminal_failure_kind(provider_failure_kind):
            return _("这次处理被系统中断了，请稍后再试。")
        if provider_failure_kind != "none":
            return _("这次处理被暂时中断了，请稍后再试一次。")
        return _("这次处理在完成前中断了。如果你愿意，我可以继续。")

    @staticmethod
    def build_completed_output(
        intents: list[IntentPlan],
        *,
        tool_results: list[ToolResult] | None = None,
        intent_results: dict[str, str] | None = None,
        reason: str = "completed",
    ) -> str:
        _reason = reason
        completed_results: list[str] = []
        completed_labels: list[str] = []
        for intent in intents:
            if intent.status != "completed":
                continue
            intent_result = RecoveryManager._intent_cached_result(
                intent,
                intent_results=intent_results,
            )
            if not intent_result:
                intent_result = RecoveryManager._intent_result_from_tool_results(
                    intent,
                    tool_results,
                )
            if intent_result:
                if intent_result not in completed_results:
                    completed_results.append(intent_result)
                continue
            display_label = str(intent.user_visible_label or "").strip()
            if display_label and display_label not in completed_labels:
                completed_labels.append(display_label)
        if completed_results:
            return " ".join(result.strip() for result in completed_results if result.strip())
        if completed_labels:
            return _("已根据现有工具结果完成：{completed}。").format(
                completed="、".join(completed_labels)
            )
        return _("我已经根据现有工具结果完成了这次请求。")

    @staticmethod
    def build_partial_response_prompt(
        intents: list[IntentPlan],
        *,
        reason: str,
        provider_failure_kind: ProviderFailureKind = "none",
        intent_results: dict[str, str] | None = None,
    ) -> ChatMessage:
        completed: list[str] = []
        unfinished: list[str] = []
        for intent in intents:
            if intent.status == "completed":
                cached_result = RecoveryManager._intent_cached_result(
                    intent, intent_results=intent_results
                )
                completed.append(cached_result or intent.user_visible_label)
            else:
                unfinished.append(intent.user_visible_label)
        return ChatMessage(
            role="system",
            content=render_prompt_contract(
                "partial_exit",
                completed_summary="；".join(completed) if completed else "无",
                unfinished_summary="；".join(unfinished) if unfinished else "无",
                exit_reason=reason,
                failure_kind=provider_failure_kind
                if provider_failure_kind != "none"
                else "orchestration_partial_exit",
            ),
        )


__all__ = ["RecoveryManager"]
