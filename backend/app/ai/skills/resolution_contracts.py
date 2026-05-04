from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillResolveIssue:
    """Structured resolver issue carried into runtime inventory diagnostics."""

    code: str
    message: str
    severity: str = "error"
    stage: str = "resolution"
    skill_id: Any | None = None
    skill_name: str = ""
    skill_type: str = ""
    package_id: Any | None = None
    package_name: str = ""
    source_plugin: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "stage": self.stage,
        }
        for key, value in (
            ("skill_id", self.skill_id),
            ("skill_name", self.skill_name),
            ("skill_type", self.skill_type),
            ("package_id", self.package_id),
            ("package_name", self.package_name),
            ("source_plugin", self.source_plugin),
        ):
            if value not in (None, ""):
                payload[key] = value
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


def make_skill_resolve_issue(
    *,
    skill: Any,
    code: str,
    message: str,
    severity: str = "error",
    stage: str = "resolution",
    source_plugin: str = "",
    metadata: dict[str, Any] | None = None,
) -> SkillResolveIssue:
    package = getattr(skill, "package", None)
    return SkillResolveIssue(
        code=code,
        message=message,
        severity=severity,
        stage=stage,
        skill_id=getattr(skill, "id", None),
        skill_name=str(getattr(skill, "name", "") or "").strip(),
        skill_type=str(getattr(skill, "type", "") or "").strip(),
        package_id=getattr(skill, "package_id", None),
        package_name=str(getattr(package, "name", "") or "").strip(),
        source_plugin=str(
            source_plugin or getattr(package, "source_plugin", "") or ""
        ).strip(),
        metadata=dict(metadata or {}),
    )


def append_skill_resolve_issue(
    result: Any,
    issue: SkillResolveIssue,
) -> None:
    issues = getattr(result, "resolution_issues", None)
    if issues is None:
        issues = []
        result.resolution_issues = issues
    issues.append(issue)

    warnings = getattr(result, "warnings", None)
    if isinstance(warnings, list) and issue.message not in warnings:
        warnings.append(issue.message)


def issue_matches_skill(
    issue: SkillResolveIssue,
    *,
    skill_id: Any | None = None,
    skill_name: str = "",
) -> bool:
    if issue.skill_id not in (None, "") and skill_id not in (None, ""):
        return issue.skill_id == skill_id
    return bool(issue.skill_name and issue.skill_name == skill_name)


__all__ = [
    "SkillResolveIssue",
    "append_skill_resolve_issue",
    "issue_matches_skill",
    "make_skill_resolve_issue",
]
