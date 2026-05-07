from __future__ import annotations

import hashlib
from typing import Any

PLUGIN_SKILL_KEY_MAX_LENGTH = 100
PLUGIN_SKILL_SOURCE_REF_MAX_LENGTH = 255


def make_plugin_skill_identity(plugin_name: str, skill_name: str) -> tuple[str, str]:
    normalized_plugin = str(plugin_name or "").strip()
    normalized_skill = str(skill_name or "").strip()
    source_ref = f"{normalized_plugin}:{normalized_skill}"
    if len(source_ref) > PLUGIN_SKILL_SOURCE_REF_MAX_LENGTH:
        raise ValueError(
            "Plugin skill identity is too long for Skill.source_ref "
            f"({len(source_ref)} > {PLUGIN_SKILL_SOURCE_REF_MAX_LENGTH})"
        )
    if len(source_ref) <= PLUGIN_SKILL_KEY_MAX_LENGTH:
        return source_ref, source_ref
    digest = hashlib.sha1(
        source_ref.encode("utf-8"), usedforsecurity=False
    ).hexdigest()[:12]
    prefix_budget = PLUGIN_SKILL_KEY_MAX_LENGTH - len(digest) - 1
    return f"{source_ref[:prefix_budget]}:{digest}", source_ref


def plugin_skill_lookup_name(skill: Any, source_plugin: str) -> str:
    prefix = f"{str(source_plugin or '').strip()}:"
    for attr in ("source_ref", "key"):
        value = str(getattr(skill, attr, "") or "").strip()
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return ""


__all__ = [
    "PLUGIN_SKILL_KEY_MAX_LENGTH",
    "PLUGIN_SKILL_SOURCE_REF_MAX_LENGTH",
    "make_plugin_skill_identity",
    "plugin_skill_lookup_name",
]
