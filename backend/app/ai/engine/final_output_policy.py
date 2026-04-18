"""Shared policy for deciding whether to append a final assistant message."""

from __future__ import annotations

from typing import Any

from app.core.i18n import _


def is_trusted_assistant_final_output_source(final_output_source: str | None) -> bool:
    return str(final_output_source or "").strip() == "assistant"


def build_untrusted_final_output_fallback(
    *,
    auto_fetch_gate_reason: str | None = None,
) -> str:
    gate_reason = str(auto_fetch_gate_reason or "").strip()
    if gate_reason in {
        "candidate_urls_exhausted",
        "search_no_results_completed",
        "search_not_successful",
    }:
        return ""
    fallback = str(_("这次处理没有成功生成最终答复，请再试一次。") or "").strip()
    return fallback or "The assistant could not finish this turn. Please retry."


def resolve_skip_final_assistant(
    *,
    response_metadata: dict[str, Any] | None,
    paused_for_consent: bool,
) -> bool:
    if paused_for_consent:
        return True
    if not response_metadata:
        return False
    return bool(response_metadata.get("skip_final_assistant"))
