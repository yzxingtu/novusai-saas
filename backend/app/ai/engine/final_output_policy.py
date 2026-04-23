"""Shared policy for deciding whether to append a final assistant message."""

from __future__ import annotations

from typing import Any

from app.core.i18n import _

TRUSTED_FINAL_OUTPUT_SOURCES = frozenset(
    {
        "assistant",
        # Deterministic recovery text built from completed tool/page evidence.
        "recovery_evidence",
    }
)


def is_trusted_assistant_final_output_source(final_output_source: str | None) -> bool:
    return str(final_output_source or "").strip() in TRUSTED_FINAL_OUTPUT_SOURCES


def build_untrusted_final_output_fallback(
    *,
    auto_fetch_gate_reason: str | None = None,
) -> str:
    gate_reason = str(auto_fetch_gate_reason or "").strip()
    if gate_reason == "search_no_results_completed":
        return str(_("我暂时没有找到可直接核实的搜索结果。") or "").strip()
    if gate_reason == "search_not_successful":
        return str(_("这次联网检索没有成功完成，请稍后再试。") or "").strip()
    if gate_reason == "candidate_urls_exhausted":
        return str(
            _(
                "我找到了候选线索，但暂时没拿到可直接核实的详情，你可以换个关键词或稍后再试。"
            )
            or ""
        ).strip()
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
