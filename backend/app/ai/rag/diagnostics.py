"""
Retriever diagnostics utilities.
"""

from __future__ import annotations

from typing import Any


def build_kb_context_diagnostics(kb_contexts: list[Any]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for ctx in kb_contexts:
        diagnostics.append(
            {
                "kb_id": int(getattr(ctx, "kb_id")),
                "weight": round(float(getattr(ctx, "weight", 1.0)), 3),
                "embedding": tuple(getattr(ctx, "embedding_signature")),
            }
        )
    return diagnostics


__all__ = ["build_kb_context_diagnostics"]
