"""Shared policy for deciding whether to append a final assistant message."""

from __future__ import annotations

from typing import Any

from app.core.i18n import _

TRUSTED_FINAL_OUTPUT_SOURCES = frozenset(
    {
        "assistant",
        "platform_fallback",
        # Deterministic recovery text built from completed tool/page evidence.
        "recovery_evidence",
    }
)


def is_trusted_assistant_final_output_source(final_output_source: str | None) -> bool:
    return str(final_output_source or "").strip() in TRUSTED_FINAL_OUTPUT_SOURCES


def build_untrusted_final_output_fallback() -> str:
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
