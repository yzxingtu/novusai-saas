from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _normalize_surface_stack(raw_stack: Any) -> list[dict[str, str]]:
    if not isinstance(raw_stack, list):
        return []
    normalized: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for item in raw_stack:
        if not isinstance(item, Mapping):
            continue
        surface_id = str(item.get("surface_id") or item.get("id") or "").strip()
        kind = str(item.get("kind") or "").strip()
        title = str(item.get("title") or "").strip()
        if not surface_id or not kind or surface_id in seen_ids:
            continue
        seen_ids.add(surface_id)
        normalized.append(
            {
                "kind": kind,
                "surface_id": surface_id,
                **({"title": title} if title else {}),
            }
        )
        if len(normalized) >= 12:
            break
    return normalized


def build_read_page_result(
    page_context: Mapping[str, Any] | None,
    *,
    snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = page_context if isinstance(page_context, Mapping) else {}
    snapshot_mapping = snapshot if isinstance(snapshot, Mapping) else {}
    surface_stack = _normalize_surface_stack(
        context.get("surface_stack") or snapshot_mapping.get("surface_stack")
    )
    active_form_summary = context.get("active_form_summary")
    snapshot_nodes = snapshot_mapping.get("nodes")
    interactables_count = snapshot_mapping.get("interactables_count")
    if not isinstance(interactables_count, int):
        interactables_count = len(snapshot_nodes) if isinstance(snapshot_nodes, list) else 0
    return {
        "active_form_summary": active_form_summary
        if isinstance(active_form_summary, Mapping)
        else None,
        "active_surface_id": str(
            context.get("active_surface_id")
            or snapshot_mapping.get("active_surface_id")
            or ""
        ).strip()
        or None,
        "interactables_count": max(interactables_count, 0),
        "page_key": str(context.get("page_key") or "").strip(),
        "page_title": str(context.get("page_title") or "").strip() or None,
        "suggested_tools": context.get("suggested_tools")
        if isinstance(context.get("suggested_tools"), Mapping)
        else None,
        "surface_stack": surface_stack,
        "ui_epoch": int(context.get("ui_epoch") or snapshot_mapping.get("ui_epoch") or 0),
    }
