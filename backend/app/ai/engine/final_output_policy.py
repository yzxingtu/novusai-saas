"""Shared policy for deciding whether to append a final assistant message."""

from __future__ import annotations

from typing import Any


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

