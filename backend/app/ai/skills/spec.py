"""
AgentScope-style skill specification parser.
AgentScope 风格的技能规格解析器。

Validates SKILL.md frontmatter and exposes the minimal normalized metadata
required by the new skill architecture.
校验 SKILL.md 前置元数据，并暴露新技能架构所需的最小归一化元数据。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

# Skill id: lowercase letters, digits, underscores only / 技能标识：仅小写字母、数字、下划线
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


class SkillSpecError(ValueError):
    """Raised when SKILL.md does not comply with the required spec. / SKILL.md 不符合必填规格时抛出。"""


@dataclass(frozen=True, slots=True)
class ParsedSkillSpec:
    """
    Normalized Skill specification extracted from SKILL.md.
    从 SKILL.md 提取的归一化技能规格。

    Attributes:
        name: Canonical skill id (pattern-validated) / 规范技能标识（已通过 pattern 校验）
        description: Trigger text for when to use the skill / 「何时使用该技能」的触发描述
        body: Markdown body after frontmatter / frontmatter 之后的 Markdown 正文
        frontmatter: Raw parsed YAML mapping / 解析后的 YAML 映射（原始结构）
    """

    name: str
    description: str
    body: str
    frontmatter: dict[str, object]


def parse_skill_markdown(markdown: str) -> ParsedSkillSpec:
    """
    Parse and validate an AgentScope-compatible SKILL.md document.
    解析并校验与 AgentScope 兼容的 SKILL.md 文档。

    Required fields / 必填字段：
    - name: lowercase letters, numbers and underscores /
      name：小写字母、数字与下划线
    - description: explicit "when to use this skill" trigger description /
      description：明确的「何时使用该技能」触发说明
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
    """Convenience alias used by schemas and services. / 供 schema 与服务层调用的便捷别名。"""
    return parse_skill_markdown(markdown)


__all__ = [
    "ParsedSkillSpec",
    "SkillSpecError",
    "SKILL_NAME_PATTERN",
    "parse_skill_markdown",
    "validate_skill_markdown",
]
