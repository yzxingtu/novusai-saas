"""Automatic project-fix loop utilities for CRUD codegen inputs. / CRUD 代码生成输入的自动修复循环工具"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

MAX_FIX_RETRIES = 3

_ALLOWED_PROJECT_KEYS = {"project_name", "entities", "cross_relations"}
_RELATION_REQUIRED_KEYS = {"source_entity", "target_entity", "relation_type"}


@dataclass(slots=True)
class FixContext:
    """Context passed to a fix function. / 传入修复函数的上下文"""

    project_dict: dict[str, Any]
    issues: list[dict[str, Any]]
    attempt: int
    max_attempts: int = MAX_FIX_RETRIES
    fix_instructions: str = ""


@dataclass(slots=True)
class FixAttempt:
    """Execution record for one auto-fix attempt. / 单次自动修复尝试的执行记录"""

    attempt: int
    success: bool
    issues_before: list[dict[str, Any]] = field(default_factory=list)
    issues_after: list[dict[str, Any]] = field(default_factory=list)
    patch: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(slots=True)
class AutoFixResult:
    """Final output for auto-fix loop. / 自动修复循环的最终结果"""

    success: bool
    fixed_project: dict[str, Any] | None = None
    attempts: list[FixAttempt] = field(default_factory=list)
    remaining_issues: list[dict[str, Any]] = field(default_factory=list)
    human_steps: list[str] = field(default_factory=list)
    total_attempts: int = 0

    def to_tool_output(self) -> dict[str, Any]:
        """Serialize to dict for tool responses. / 序列化为工具响应用字典"""
        return {
            "success": self.success,
            "fixed_project": self.fixed_project,
            "attempts": [a.__dict__ for a in self.attempts],
            "remaining_issues": self.remaining_issues,
            "human_steps": self.human_steps,
            "total_attempts": self.total_attempts,
        }


def validate_project(
    project_dict: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate codegen project data and return (valid, issues, warnings). / 校验代码生成项目数据，返回 (是否有效, 问题列表, 警告列表)"""
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    extra_keys = sorted(set(project_dict.keys()) - _ALLOWED_PROJECT_KEYS)
    if extra_keys:
        issues.append(
            {
                "code": "invalid_extra_field",
                "message": f"Unexpected top-level keys: {', '.join(extra_keys)}",
            }
        )

    project_name = project_dict.get("project_name")
    if not isinstance(project_name, str) or not project_name.strip():
        issues.append(
            {"code": "invalid_project_name", "message": "project_name is required"}
        )

    entities = project_dict.get("entities")
    if not isinstance(entities, list) or not entities:
        issues.append({"code": "invalid_entities", "message": "entities is required"})
        return False, issues, warnings

    entity_modules: set[str] = set()
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            issues.append(
                {
                    "code": "invalid_entity",
                    "message": f"Entity at index {index} must be an object",
                }
            )
            continue

        module = str(entity.get("module", "")).strip()
        table_name = str(entity.get("table_name", "")).strip()
        display_name = str(entity.get("display_name", "")).strip()

        if not module or not table_name or not display_name:
            issues.append(
                {
                    "code": "invalid_entity",
                    "message": f"Entity at index {index} missing required fields",
                }
            )
            continue

        if module in entity_modules:
            issues.append(
                {
                    "code": "duplicate_entity_module",
                    "message": f"Duplicate entity module: {module}",
                }
            )
        entity_modules.add(module)

    _validate_relations(project_dict, entity_modules, issues)
    _validate_relation_cycles(project_dict, entity_modules, issues)

    return len(issues) == 0, issues, warnings


def build_fix_instructions(issues: list[dict[str, Any]]) -> str:
    """Build plain-text instructions for a fix function. / 为修复函数生成纯文本指令"""
    if not issues:
        return ""

    lines: list[str] = ["Fix the following validation issues:"]
    for idx, issue in enumerate(issues, start=1):
        code = str(issue.get("code", "unknown"))
        message = str(issue.get("message", ""))
        lines.append(f"{idx}. [{code}] {message}")
        related_nodes = issue.get("related_nodes")
        if isinstance(related_nodes, list) and related_nodes:
            lines.append(f"   related_nodes: {', '.join(str(n) for n in related_nodes)}")
    return "\n".join(lines)


def suggest_human_steps(issues: list[dict[str, Any]]) -> list[str]:
    """Generate actionable human fallback steps from remaining issues. / 根据剩余问题生成可执行的人工处理步骤"""
    if not issues:
        return ["Review the generated project schema before running code generation."]

    steps: list[str] = []
    for issue in issues:
        code = str(issue.get("code", "")).lower()
        if "cycle" in code:
            steps.append(
                "Resolve circular relation dependencies by removing one belongs_to link."
            )
        elif "missing_entity" in code:
            steps.append(
                "Add the missing entity definition or correct relation target names."
            )
        elif "extra_field" in code:
            steps.append("Remove unsupported top-level fields from the project payload.")
        else:
            steps.append(
                "Review invalid nodes and align them with the project schema requirements."
            )

    deduped: list[str] = []
    seen: set[str] = set()
    for step in steps:
        if step not in seen:
            deduped.append(step)
            seen.add(step)
    return deduped


def build_fix_context(
    project_dict: dict[str, Any],
    issues: list[dict[str, Any]],
    attempt: int,
    max_attempts: int = MAX_FIX_RETRIES,
) -> FixContext:
    """Create a FixContext for one retry iteration. / 为一次重试迭代创建 FixContext"""
    return FixContext(
        project_dict=project_dict,
        issues=issues,
        attempt=attempt,
        max_attempts=max_attempts,
        fix_instructions=build_fix_instructions(issues),
    )


def apply_fix_patch(project_dict: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a partial patch to project data with entity upsert semantics. / 按实体 upsert 语义将补丁应用到项目数据"""
    if not patch:
        return {
            "project_name": project_dict.get("project_name"),
            "entities": list(project_dict.get("entities", [])),
            "cross_relations": list(project_dict.get("cross_relations", [])),
        }

    merged: dict[str, Any] = {
        "project_name": project_dict.get("project_name"),
        "entities": list(project_dict.get("entities", [])),
        "cross_relations": list(project_dict.get("cross_relations", [])),
    }

    for key, value in patch.items():
        if key == "entities" and isinstance(value, list):
            merged["entities"] = _merge_entities(merged["entities"], value)
        elif key == "cross_relations" and isinstance(value, list):
            merged["cross_relations"] = _merge_relations(merged["cross_relations"], value)
        else:
            merged[key] = value

    return merged


def run_fix_loop(
    project_dict: dict[str, Any],
    fix_fn: Callable[[FixContext], dict[str, Any] | None] | None = None,
    max_retries: int = MAX_FIX_RETRIES,
) -> AutoFixResult:
    """Run validation + optional fix function retries until success or exhausted. / 运行校验与可选修复循环直至成功或耗尽"""
    valid, issues, _warnings = validate_project(project_dict)
    if valid:
        return AutoFixResult(
            success=True,
            fixed_project=project_dict,
            total_attempts=0,
        )

    if fix_fn is None:
        return AutoFixResult(
            success=False,
            fixed_project=project_dict,
            remaining_issues=issues,
            human_steps=suggest_human_steps(issues),
            total_attempts=0,
        )

    attempts: list[FixAttempt] = []
    current_project = project_dict
    current_issues = issues

    for attempt_no in range(1, max_retries + 1):
        ctx = build_fix_context(
            project_dict=current_project,
            issues=current_issues,
            attempt=attempt_no,
            max_attempts=max_retries,
        )

        try:
            patch = fix_fn(ctx) or {}
        except Exception as exc:  # noqa: BLE001
            attempts.append(
                FixAttempt(
                    attempt=attempt_no,
                    success=False,
                    issues_before=current_issues,
                    issues_after=current_issues,
                    patch={},
                    error=str(exc),
                )
            )
            continue

        fixed_project = apply_fix_patch(current_project, patch)
        valid, next_issues, _warnings = validate_project(fixed_project)

        attempts.append(
            FixAttempt(
                attempt=attempt_no,
                success=valid,
                issues_before=current_issues,
                issues_after=next_issues,
                patch=patch,
            )
        )

        current_project = fixed_project
        current_issues = next_issues

        if valid:
            return AutoFixResult(
                success=True,
                fixed_project=current_project,
                attempts=attempts,
                total_attempts=len(attempts),
            )

    return AutoFixResult(
        success=False,
        fixed_project=current_project,
        attempts=attempts,
        remaining_issues=current_issues,
        human_steps=suggest_human_steps(current_issues),
        total_attempts=len(attempts),
    )


def _validate_relations(
    project_dict: dict[str, Any],
    entity_modules: set[str],
    issues: list[dict[str, Any]],
) -> None:
    relations = project_dict.get("cross_relations", [])
    if relations is None:
        return
    if not isinstance(relations, list):
        issues.append(
            {"code": "invalid_relations", "message": "cross_relations must be a list"}
        )
        return

    for index, rel in enumerate(relations):
        if not isinstance(rel, dict):
            issues.append(
                {
                    "code": "invalid_relation",
                    "message": f"Relation at index {index} must be an object",
                }
            )
            continue

        if not _RELATION_REQUIRED_KEYS.issubset(rel.keys()):
            issues.append(
                {
                    "code": "invalid_relation",
                    "message": f"Relation at index {index} missing required fields",
                }
            )
            continue

        source = str(rel.get("source_entity", "")).strip()
        target = str(rel.get("target_entity", "")).strip()

        if source not in entity_modules or target not in entity_modules:
            missing = source if source not in entity_modules else target
            issues.append(
                {
                    "code": "missing_entity",
                    "message": f"Entity '{missing}' not found",
                    "related_nodes": [source, target],
                }
            )


def _validate_relation_cycles(
    project_dict: dict[str, Any],
    entity_modules: set[str],
    issues: list[dict[str, Any]],
) -> None:
    relations = project_dict.get("cross_relations")
    if not isinstance(relations, list) or not relations:
        return

    graph: dict[str, set[str]] = {module: set() for module in entity_modules}
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        source = str(rel.get("source_entity", "")).strip()
        target = str(rel.get("target_entity", "")).strip()
        if source in entity_modules and target in entity_modules:
            graph[source].add(target)

    visited: set[str] = set()
    stack: list[str] = []
    stack_set: set[str] = set()

    seen_cycles: set[tuple[str, ...]] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        stack.append(node)
        stack_set.add(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in stack_set:
                cycle_start = stack.index(neighbor)
                cycle_nodes = tuple(stack[cycle_start:] + [neighbor])
                cycle_normalized = tuple(
                    min(cycle_nodes[i:] + cycle_nodes[:i] for i in range(len(cycle_nodes)))
                )
                if cycle_normalized not in seen_cycles:
                    seen_cycles.add(cycle_normalized)
                    issues.append(
                        {
                            "code": "cycle_detected",
                            "message": f"Cycle detected: {' -> '.join(cycle_nodes)}",
                            "related_nodes": list(cycle_nodes[:-1]),
                        }
                    )
        stack.pop()
        stack_set.remove(node)

    for module in graph:
        if module not in visited:
            dfs(module)


def _merge_entities(
    base_entities: list[dict[str, Any]],
    patch_entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(entity) for entity in base_entities if isinstance(entity, dict)]
    index_by_module: dict[str, int] = {}
    for idx, entity in enumerate(merged):
        module = str(entity.get("module", "")).strip()
        if module:
            index_by_module[module] = idx

    for entity in patch_entities:
        if not isinstance(entity, dict):
            continue
        module = str(entity.get("module", "")).strip()
        if module and module in index_by_module:
            merged[index_by_module[module]] = dict(entity)
        else:
            if module:
                index_by_module[module] = len(merged)
            merged.append(dict(entity))

    return merged


def _merge_relations(
    base_relations: list[dict[str, Any]],
    patch_relations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(rel) for rel in base_relations if isinstance(rel, dict)]
    existing: set[tuple[str, str, str]] = set()
    for rel in merged:
        existing.add(
            (
                str(rel.get("source_entity", "")),
                str(rel.get("target_entity", "")),
                str(rel.get("relation_type", "")),
            )
        )

    for rel in patch_relations:
        if not isinstance(rel, dict):
            continue
        key = (
            str(rel.get("source_entity", "")),
            str(rel.get("target_entity", "")),
            str(rel.get("relation_type", "")),
        )
        if key in existing:
            continue
        merged.append(dict(rel))
        existing.add(key)

    return merged


__all__ = [
    "MAX_FIX_RETRIES",
    "AutoFixResult",
    "FixAttempt",
    "FixContext",
    "apply_fix_patch",
    "build_fix_context",
    "build_fix_instructions",
    "run_fix_loop",
    "suggest_human_steps",
    "validate_project",
]
