from __future__ import annotations

import hashlib
from typing import Any


def make_plugin_skill_identity(plugin_name: str, skill_name: str) -> tuple[str, str]:
    normalized_plugin = str(plugin_name or "").strip()
    normalized_skill = str(skill_name or "").strip()
    source_ref = f"{normalized_plugin}:{normalized_skill}"
    if len(source_ref) <= 100:
        return source_ref, source_ref
    digest = hashlib.sha1(source_ref.encode("utf-8")).hexdigest()[:12]
    return f"{source_ref[:87]}:{digest}", source_ref


def plugin_skill_lookup_name(skill: Any, source_plugin: str) -> str:
    prefix = f"{str(source_plugin or '').strip()}:"
    for attr in ("source_ref", "key"):
        value = str(getattr(skill, attr, "") or "").strip()
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return ""


__all__ = [
    "make_plugin_skill_identity",
    "plugin_skill_lookup_name",
]
