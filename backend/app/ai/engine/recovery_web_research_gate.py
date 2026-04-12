"""Web research recovery gating helpers."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _

from .recovery_result_normalizer import RecoveryResultNormalizer
from .recovery_tool_result_helpers import (
    extract_fetch_url_candidate_urls,
    latest_successful_tool_result,
    tool_attempted,
    web_search_result_count,
)
from .types import IntentPlan


class RecoveryWebResearchGate:
    """Recovery helpers for web_research intents."""

    @staticmethod
    def normalized_url_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            url = str(item or "").strip()
            if url and url not in normalized:
                normalized.append(url)
        return normalized

    @staticmethod
    def extract_fetch_url_candidate_urls(
        tool_results: list[ToolResult] | None,
    ) -> list[str]:
        return extract_fetch_url_candidate_urls(tool_results)

    @staticmethod
    def sync_fetch_url_candidates(
        intent: IntentPlan,
        tool_results: list[ToolResult] | None = None,
    ) -> None:
        if str(intent.family or "").strip() != "web_research":
            return
        candidate_urls = RecoveryWebResearchGate.extract_fetch_url_candidate_urls(
            tool_results
        )
        if not candidate_urls:
            return
        metadata = dict(intent.metadata or {})
        existing_urls = RecoveryWebResearchGate.normalized_url_list(
            metadata.get("fetch_url_candidate_urls")
        )
        merged_urls = list(existing_urls)
        for url in candidate_urls:
            if url not in merged_urls:
                merged_urls.append(url)
        metadata["fetch_url_candidate_urls"] = merged_urls
        metadata["fetch_url_attempted_urls"] = RecoveryWebResearchGate.normalized_url_list(
            metadata.get("fetch_url_attempted_urls")
        )
        metadata["fetch_url_blocked_urls"] = RecoveryWebResearchGate.normalized_url_list(
            metadata.get("fetch_url_blocked_urls")
        )
        intent.metadata = metadata

    @staticmethod
    def latest_successful_tool_result(
        tool_name: str,
        tool_results: list[ToolResult] | None = None,
    ) -> ToolResult | None:
        return latest_successful_tool_result(tool_name, tool_results)

    @staticmethod
    def web_search_result_count(
        tool_results: list[ToolResult] | None = None,
    ) -> int | None:
        return web_search_result_count(tool_results)

    @staticmethod
    def set_auto_fetch_gate_reason(intent: IntentPlan, reason: str) -> None:
        metadata = dict(intent.metadata or {})
        metadata["auto_fetch_gate_reason"] = str(reason or "").strip() or None
        if metadata["auto_fetch_gate_reason"] is None:
            metadata.pop("auto_fetch_gate_reason", None)
        intent.metadata = metadata

    @staticmethod
    def clear_requires_fetch_url(intent: IntentPlan, *, reason: str) -> None:
        metadata = dict(intent.metadata or {})
        metadata.pop("requires_fetch_url", None)
        metadata["auto_fetch_gate_reason"] = str(reason or "").strip() or None
        intent.metadata = metadata

    @staticmethod
    def web_research_no_result_output(intent: IntentPlan) -> str:
        label = str(intent.user_visible_label or "").strip()
        if RecoveryResultNormalizer._should_prefix_result_with_label(label):
            return _("关于{label}，我暂时没有找到可直接核实的搜索结果。").format(
                label=label
            )
        return _("我暂时没有找到可直接核实的搜索结果。")

    @staticmethod
    def is_completed_web_research_no_result(
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
        candidate_urls = RecoveryWebResearchGate.normalized_url_list(
            (intent.metadata or {}).get("fetch_url_candidate_urls")
        )
        if candidate_urls:
            return False
        if tool_attempted(messages, "fetch_url", tool_results=tool_results):
            return False
        result_count = RecoveryWebResearchGate.web_search_result_count(tool_results)
        if result_count is None:
            return True
        return result_count <= 0

    @staticmethod
    def force_fetch_url_after_search(
        intent: IntentPlan,
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
        successful_tool_names: set[str],
    ) -> None:
        if str(intent.family or "").strip() != "web_research":
            return

        RecoveryWebResearchGate.sync_fetch_url_candidates(intent, tool_results)
        metadata = dict(intent.metadata or {})
        candidate_urls = RecoveryWebResearchGate.normalized_url_list(
            metadata.get("fetch_url_candidate_urls")
        )
        attempted_urls = set(
            RecoveryWebResearchGate.normalized_url_list(
                metadata.get("fetch_url_attempted_urls")
            )
        )
        remaining_candidate_urls = [
            url for url in candidate_urls if url not in attempted_urls
        ]
        result_count = RecoveryWebResearchGate.web_search_result_count(tool_results)
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
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="search_not_successful",
            )
            return
        if result_count is not None and result_count <= 0:
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="search_no_results",
            )
            return
        if not candidate_urls:
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="no_candidate_urls",
            )
            return
        if tool_attempted(messages, "fetch_url", tool_results=tool_results):
            RecoveryWebResearchGate.clear_requires_fetch_url(
                intent,
                reason="fetch_already_attempted",
            )
            return
        if not remaining_candidate_urls:
            RecoveryWebResearchGate.clear_requires_fetch_url(
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
    def complete_native_search_intents(intents: list[IntentPlan]) -> list[IntentPlan]:
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


__all__ = ["RecoveryWebResearchGate"]
