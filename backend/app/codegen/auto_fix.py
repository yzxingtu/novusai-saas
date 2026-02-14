"""
AI 自动修复 Loop — validate → fix → revalidate

M58-T21: 批量配置自动修复闭环

当 validate 返回错误时，构建修复上下文供 AI 生成 patch，
merge_patch 后重新校验，最多 N 次，失败则返回结构化问题。

流程：
1. validate(project) → issues
2. 若 issues → 构建 fix_context → AI 生成 patch
3. merge_patch(project, patch) → merged_project
4. validate(merged_project) → issues
5. 重复 2-4 最多 MAX_FIX_RETRIES 次
6. 失败 → 返回 {issues, last_patch, human_steps}
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# Type alias for the fix function
FixFn = Callable[["FixContext"], dict[str, Any]]


# ============================================================
# 配置
# ============================================================

MAX_FIX_RETRIES = 3
"""最大自动修复重试次数"""


# ============================================================
# Fix 上下文（给 AI 的输入）
# ============================================================


class FixContext(BaseModel):
    """自动修复上下文 — 传给 AI 的输入"""

    project: dict[str, Any] = Field(..., description="当前项目 JSON")
    issues: list[dict[str, Any]] = Field(
        default_factory=list, description="待修复的 issues",
    )
    warnings: list[dict[str, Any]] = Field(
        default_factory=list, description="待关注的 warnings",
    )
    attempt: int = Field(1, description="当前修复轮次 (1-based)")
    max_attempts: int = Field(MAX_FIX_RETRIES)
    fix_instructions: str = Field(
        "",
        description="修复指令（由 build_fix_context 生成）",
    )


# ============================================================
# Fix 结果
# ============================================================


class FixAttempt(BaseModel):
    """单次修复尝试记录"""

    attempt: int = Field(..., description="轮次")
    issues_before: int = Field(0, description="修复前 issue 数")
    issues_after: int = Field(0, description="修复后 issue 数")
    patch_applied: dict[str, Any] = Field(
        default_factory=dict, description="本轮应用的 patch",
    )
    fixed: bool = Field(False, description="本轮是否修复成功")
    error_message: str | None = Field(None, description="异常错误信息")


class AutoFixResult(BaseModel):
    """自动修复最终结果"""

    success: bool = Field(False, description="是否全部修复")
    project: dict[str, Any] = Field(
        default_factory=dict, description="最终项目 JSON",
    )
    attempts: list[FixAttempt] = Field(
        default_factory=list, description="修复尝试历史",
    )
    remaining_issues: list[dict[str, Any]] = Field(
        default_factory=list, description="剩余未解决的 issues",
    )
    human_steps: list[str] = Field(
        default_factory=list,
        description="建议的人工处理步骤",
    )
    total_attempts: int = Field(0)

    def to_tool_output(self) -> dict[str, Any]:
        """序列化为工具输出"""
        return self.model_dump(mode="json")


# ============================================================
# 修复指令生成
# ============================================================


def build_fix_instructions(issues: list[dict[str, Any]]) -> str:
    """根据 issues 构建修复指令

    Args:
        issues: GraphIssue 或 GuardResult.invalid_fields 的 dict 列表

    Returns:
        修复指令字符串（用于 AI prompt）
    """
    if not issues:
        return ""

    lines = ["Fix the following issues in the BatchCrudProject:"]
    for i, issue in enumerate(issues, 1):
        code = issue.get("code", "unknown")
        msg = issue.get("message", "")
        related = issue.get("related_nodes", [])

        line = f"{i}. [{code}] {msg}"
        if related:
            line += f" (entities: {', '.join(related)})"
        lines.append(line)

    lines.append("")
    lines.append("Rules:")
    lines.append("- Output a valid patch object with corrected entities/relations")
    lines.append("- Do NOT add fields not in the schema")
    lines.append("- Do NOT remove existing valid entities unless necessary")
    lines.append("- Fix dependency cycles by removing or reversing edges")
    lines.append("- Fix missing entity references by adding the entity or removing the relation")

    return "\n".join(lines)


def build_fix_context(
    project_dict: dict[str, Any],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]] | None = None,
    attempt: int = 1,
) -> FixContext:
    """构建修复上下文

    Args:
        project_dict: 当前项目 JSON
        issues: 待修复的 issues
        warnings: 待关注的 warnings
        attempt: 当前轮次

    Returns:
        FixContext（传给 AI 的完整上下文）
    """
    return FixContext(
        project=project_dict,
        issues=issues,
        warnings=warnings or [],
        attempt=attempt,
        max_attempts=MAX_FIX_RETRIES,
        fix_instructions=build_fix_instructions(issues),
    )


# ============================================================
# 人工步骤建议
# ============================================================


def suggest_human_steps(issues: list[dict[str, Any]]) -> list[str]:
    """根据无法自动修复的 issues 生成人工处理建议

    Args:
        issues: 剩余未修复的 issues

    Returns:
        人工处理步骤列表
    """
    steps: list[str] = []

    for issue in issues:
        code = issue.get("code", "")
        msg = issue.get("message", "")
        related = issue.get("related_nodes", [])

        if "cycle" in code.lower():
            entities_str = ", ".join(related) if related else "related entities"
            steps.append(
                f"Review circular dependency between {entities_str}. "
                f"Consider removing or redesigning one of the relations."
            )
        elif "missing" in code.lower():
            steps.append(
                f"Add the missing entity referenced in: {msg}"
            )
        elif "duplicate" in code.lower():
            steps.append(
                f"Resolve duplicate: {msg}"
            )
        elif "conflict" in code.lower():
            steps.append(
                f"Resolve conflict: {msg}"
            )
        else:
            steps.append(f"Manually review: {msg}")

    if not steps:
        steps.append(
            "Review the remaining issues and adjust the project configuration manually."
        )

    return steps


# ============================================================
# 校验 + 修复编排（同步，不调 AI）
# ============================================================


def validate_project(project_dict: dict[str, Any]) -> tuple[bool, list[dict], list[dict]]:
    """校验项目并返回 (valid, issues, warnings)

    This is a convenience wrapper that runs schema guard + project graph validation.
    """
    from app.codegen.schema_guard import guard_batch_project

    # 1. Schema guard
    guard = guard_batch_project(project_dict)
    if not guard.valid:
        issues = [
            {
                "code": f.error_type.value,
                "message": f.reason,
                "related_nodes": [f.path],
            }
            for f in guard.invalid_fields
        ]
        return False, issues, []

    # 2. Project graph validation
    from app.codegen.project_graph import build_project_graph
    from app.codegen.schemas import BatchCrudProject

    project = BatchCrudProject(**project_dict)
    graph = build_project_graph(project)

    issues = [i.model_dump(mode="json") for i in graph.issues]
    warnings = [w.model_dump(mode="json") for w in graph.warnings]

    return graph.valid, issues, warnings


def apply_fix_patch(
    project_dict: dict[str, Any],
    patch_dict: dict[str, Any],
) -> dict[str, Any]:
    """应用修复 patch 到项目

    Args:
        project_dict: 当前项目 JSON
        patch_dict: 修复 patch JSON

    Returns:
        合并后的项目 JSON
    """
    from app.codegen.batch_merge import BatchMergePatch, merge_batch_project
    from app.codegen.schemas import BatchCrudProject

    project = BatchCrudProject(**project_dict)
    patch = BatchMergePatch(**patch_dict)

    result = merge_batch_project(project, patch)
    return result.project.model_dump(mode="json")


def run_fix_loop(
    project_dict: dict[str, Any],
    fix_fn: FixFn | None = None,
    max_retries: int = MAX_FIX_RETRIES,
) -> AutoFixResult:
    """执行自动修复循环（同步版，fix_fn 可选）

    如果没有 fix_fn（即没有 AI），仅校验并返回结果。
    如果有 fix_fn，每轮调用 fix_fn(FixContext) -> patch_dict。

    Args:
        project_dict: 初始项目 JSON
        fix_fn: 修复函数 (FixContext) -> dict[str, Any] (patch)
                None = 仅校验不修复
        max_retries: 最大重试次数

    Returns:
        AutoFixResult
    """
    current = project_dict
    attempts: list[FixAttempt] = []

    # 初始校验
    valid, issues, warnings = validate_project(current)
    if valid:
        return AutoFixResult(
            success=True,
            project=current,
            total_attempts=0,
        )

    if fix_fn is None:
        return AutoFixResult(
            success=False,
            project=current,
            remaining_issues=issues,
            human_steps=suggest_human_steps(issues),
            total_attempts=0,
        )

    # 修复循环
    for attempt_num in range(1, max_retries + 1):
        ctx = build_fix_context(
            project_dict=current,
            issues=issues,
            warnings=warnings,
            attempt=attempt_num,
        )

        # AI 生成 patch
        try:
            patch_dict = fix_fn(ctx)
        except Exception as exc:
            logger.warning(
                "fix_fn failed at attempt %d: %s", attempt_num, exc,
            )
            attempts.append(FixAttempt(
                attempt=attempt_num,
                issues_before=len(issues),
                issues_after=len(issues),
                fixed=False,
                error_message=str(exc),
            ))
            break

        if not patch_dict:
            attempts.append(FixAttempt(
                attempt=attempt_num,
                issues_before=len(issues),
                issues_after=len(issues),
                fixed=False,
            ))
            break

        # 应用 patch
        try:
            current = apply_fix_patch(current, patch_dict)
        except Exception as exc:
            logger.warning(
                "apply_fix_patch failed at attempt %d: %s",
                attempt_num, exc,
            )
            attempts.append(FixAttempt(
                attempt=attempt_num,
                issues_before=len(issues),
                issues_after=len(issues),
                patch_applied=patch_dict,
                fixed=False,
                error_message=str(exc),
            ))
            break

        # 重新校验
        new_valid, new_issues, new_warnings = validate_project(current)

        attempts.append(FixAttempt(
            attempt=attempt_num,
            issues_before=len(issues),
            issues_after=len(new_issues),
            patch_applied=patch_dict,
            fixed=new_valid,
        ))

        if new_valid:
            return AutoFixResult(
                success=True,
                project=current,
                attempts=attempts,
                total_attempts=attempt_num,
            )

        issues = new_issues
        warnings = new_warnings

    # 耗尽重试
    return AutoFixResult(
        success=False,
        project=current,
        attempts=attempts,
        remaining_issues=issues,
        human_steps=suggest_human_steps(issues),
        total_attempts=len(attempts),
    )


__all__ = [
    "MAX_FIX_RETRIES",
    "AutoFixResult",
    "FixAttempt",
    "FixContext",
    "FixFn",
    "apply_fix_patch",
    "build_fix_context",
    "build_fix_instructions",
    "run_fix_loop",
    "suggest_human_steps",
    "validate_project",
]
