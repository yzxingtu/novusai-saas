"""Plugin slot access helpers.

Keep frontend slot exposure aligned with the current user's permission set so
the host does not register routes that the same user can never enter.
"""

from __future__ import annotations

from typing import Any


def filter_grouped_plugin_slots_by_permission_codes(
    grouped: dict[str, list[dict[str, Any]]],
    permission_codes: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Filter grouped slot payload by slot-level access codes.

    Non-route slots without ``access_codes`` stay visible. Standalone page slots
    are protected route entries, so missing or empty ``access_codes`` are hidden
    unless the user has ``*``.
    """

    normalized_codes = {
        code.strip()
        for code in permission_codes
        if isinstance(code, str) and code.strip()
    }
    if "*" in normalized_codes:
        return grouped

    filtered: dict[str, list[dict[str, Any]]] = {}
    for slot_key, slots in grouped.items():
        visible_slots: list[dict[str, Any]] = []
        for slot in slots:
            raw_access_codes = slot.get("access_codes")
            if not isinstance(raw_access_codes, list) or len(raw_access_codes) == 0:
                if slot_key == "pages":
                    continue
                visible_slots.append(slot)
                continue

            slot_access_codes = [
                code.strip()
                for code in raw_access_codes
                if isinstance(code, str) and code.strip()
            ]
            if not slot_access_codes:
                if slot_key == "pages":
                    continue
                visible_slots.append(slot)
                continue

            if any(code in normalized_codes for code in slot_access_codes):
                visible_slots.append(slot)

        filtered[slot_key] = visible_slots

    return filtered


def collect_plugin_names_from_grouped_slots(
    grouped: dict[str, list[dict[str, Any]]],
) -> set[str]:
    """Collect plugin names that still have visible frontend surfaces."""

    plugin_names: set[str] = set()
    for slots in grouped.values():
        for slot in slots:
            plugin_name = slot.get("plugin_name")
            if isinstance(plugin_name, str) and plugin_name.strip():
                plugin_names.add(plugin_name.strip())
    return plugin_names
