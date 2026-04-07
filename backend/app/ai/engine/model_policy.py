"""Model request policy helpers shared by sync and stream execution."""

from __future__ import annotations

from typing import Any

FAST_PATH_REASONING_EFFORT = "low"


def build_model_request_overrides(
    *,
    execution_path: str | None,
    tools: list[Any] | None,
) -> dict[str, Any]:
    """Apply lightweight model overrides for fast, text-only rounds."""

    normalized_path = str(execution_path or "").strip().lower()
    if normalized_path != "fast":
        return {}
    if tools:
        return {}
    return {
        "_runtime_reasoning_effort_override": FAST_PATH_REASONING_EFFORT,
    }


__all__ = ["FAST_PATH_REASONING_EFFORT", "build_model_request_overrides"]
