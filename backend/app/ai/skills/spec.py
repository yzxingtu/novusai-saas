"""
AgentScope-style skill specification parser.

Validates SKILL.md frontmatter and exposes the minimal normalized metadata
required by the new skill architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


class SkillSpecError(ValueError):
    """Raised when SKILL.md does not comply with the required spec."""


@dataclass(frozen=True, slots=True)
class ParsedSkillSpec:
    """Normalized Skill specification extracted from SKILL.md."""

    name: str
    description: str
    body: str
    frontmatter: dict[str, object]


def parse_skill_markdown(markdown: str) -> ParsedSkillSpec:
    """
    Parse and validate an AgentScope-compatible SKILL.md document.

    Required fields:
    - name: lowercase letters, numbers and underscores
    - description: explicit "when to use this skill" trigger description
    """
    source = (markdown or "").strip()
    if not source:
        raise SkillSpecError("SKILL.md content cannot be empty")

    if not source.startswith("---"):
        raise SkillSpecError("SKILL.md must start with YAML frontmatter")

    parts = source.split("---", 2)
    if len(parts) < 3:
        raise SkillSpecError("SKILL.md frontmatter is not closed correctly")

    raw_frontmatter = parts[1].strip()
    body = parts[2].lstrip()
    if not body:
        raise SkillSpecError("SKILL.md body cannot be empty")

    try:
        frontmatter = yaml.safe_load(raw_frontmatter) or {}
    except yaml.YAMLError as exc:
        raise SkillSpecError(f"Invalid SKILL.md frontmatter: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise SkillSpecError("SKILL.md frontmatter must be a YAML mapping")

    raw_name = str(frontmatter.get("name", "")).strip()
    if not raw_name:
        raise SkillSpecError("SKILL.md frontmatter must include 'name'")
    if not SKILL_NAME_PATTERN.fullmatch(raw_name):
        raise SkillSpecError(
            "SKILL.md name must contain only lowercase letters, numbers, and underscores"
        )

    raw_description = str(frontmatter.get("description", "")).strip()
    if not raw_description:
        raise SkillSpecError("SKILL.md frontmatter must include 'description'")

    return ParsedSkillSpec(
        name=raw_name,
        description=raw_description,
        body=body,
        frontmatter=frontmatter,
    )


def validate_skill_markdown(markdown: str) -> ParsedSkillSpec:
    """Convenience alias used by schemas and services."""
    return parse_skill_markdown(markdown)


__all__ = [
    "ParsedSkillSpec",
    "SkillSpecError",
    "SKILL_NAME_PATTERN",
    "parse_skill_markdown",
    "validate_skill_markdown",
]
