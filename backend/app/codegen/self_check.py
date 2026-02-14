"""
生成后自检 — quick static validate

M58-T32: 在写盘后提供快速自检，尽早发现路由未注册、
export 缺失、重复注册、语法错误等问题。

自检规则：
1. 路由注册一致性（生成的模块是否在 router 中注册）
2. API export 一致性（生成的 API 文件是否在聚合文件中导出）
3. 重复注册检查（同一模块是否注册多次）
4. Python AST 语法校验
5. 后端 router init 一致性
"""

from __future__ import annotations

import ast
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 自检结果模型
# ============================================================


class CheckSeverity(str, Enum):
    """检查严重性"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class CheckCode(str, Enum):
    """检查错误码"""

    ROUTE_MISSING = "route_missing"
    ROUTE_DUPLICATE = "route_duplicate"
    EXPORT_MISSING = "export_missing"
    EXPORT_DUPLICATE = "export_duplicate"
    SYNTAX_ERROR = "syntax_error"
    BACKEND_ROUTE_MISSING = "backend_route_missing"
    FILE_NOT_FOUND = "file_not_found"


class CheckIssue(BaseModel):
    """自检问题"""

    severity: CheckSeverity = Field(CheckSeverity.ERROR)
    code: CheckCode = Field(...)
    path: str = Field("", description="相关文件路径")
    message: str = Field(...)
    hint: str = Field("", description="修复提示")


class SelfCheckResult(BaseModel):
    """自检结果"""

    passed: bool = Field(True)
    issues: list[CheckIssue] = Field(default_factory=list)
    checks_run: int = Field(0)
    error_count: int = Field(0)
    warning_count: int = Field(0)

    def to_tool_output(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ============================================================
# 检查函数
# ============================================================


def check_frontend_routes(
    generated_modules: list[str],
    router_content: str,
) -> list[CheckIssue]:
    """检查前端路由注册一致性

    Args:
        generated_modules: 已生成的模块名列表
        router_content: 前端 router 聚合文件内容

    Returns:
        问题列表
    """
    issues: list[CheckIssue] = []

    for module in generated_modules:
        # 检查 module 是否在 router 中（import 或 path）
        patterns = [
            module.replace("-", "_"),
            module.replace("_", "-"),
            module,
        ]
        found = any(p in router_content for p in patterns)

        if not found:
            issues.append(CheckIssue(
                severity=CheckSeverity.ERROR,
                code=CheckCode.ROUTE_MISSING,
                path="router/routes",
                message=f"Module '{module}' is not registered in the frontend router.",
                hint=f"Add a route import/definition for '{module}' in the router file.",
            ))

    # 重复检查
    _check_duplicates(
        router_content,
        generated_modules,
        CheckCode.ROUTE_DUPLICATE,
        "route",
        issues,
    )

    return issues


def check_frontend_exports(
    generated_modules: list[str],
    export_content: str,
) -> list[CheckIssue]:
    """检查前端 API export 一致性

    Args:
        generated_modules: 已生成的模块名列表
        export_content: API 聚合导出文件内容

    Returns:
        问题列表
    """
    issues: list[CheckIssue] = []

    for module in generated_modules:
        patterns = [
            module.replace("-", "_"),
            module.replace("_", "-"),
            module,
        ]
        found = any(p in export_content for p in patterns)

        if not found:
            issues.append(CheckIssue(
                severity=CheckSeverity.WARNING,
                code=CheckCode.EXPORT_MISSING,
                path="api/index",
                message=f"Module '{module}' API is not exported in the aggregation file.",
                hint=f"Add 'export * from './{module}'' to the API index file.",
            ))

    _check_duplicates(
        export_content,
        generated_modules,
        CheckCode.EXPORT_DUPLICATE,
        "API export",
        issues,
    )

    return issues


def check_backend_routes(
    generated_modules: list[str],
    router_init_content: str,
) -> list[CheckIssue]:
    """检查后端 router init 一致性

    Args:
        generated_modules: 已生成的模块名列表
        router_init_content: 后端 router __init__.py 内容

    Returns:
        问题列表
    """
    issues: list[CheckIssue] = []

    for module in generated_modules:
        patterns = [
            module.replace("-", "_"),
            module,
        ]
        found = any(p in router_init_content for p in patterns)

        if not found:
            issues.append(CheckIssue(
                severity=CheckSeverity.ERROR,
                code=CheckCode.BACKEND_ROUTE_MISSING,
                path="api/__init__.py",
                message=f"Module '{module}' is not registered in the backend router init.",
                hint=f"Add 'from .{module} import router' to the backend __init__.py.",
            ))

    return issues


def check_python_syntax(files: dict[str, str]) -> list[CheckIssue]:
    """检查 Python 文件语法

    Args:
        files: {path: content} 的 Python 文件

    Returns:
        问题列表
    """
    issues: list[CheckIssue] = []

    for path, content in files.items():
        if not path.endswith(".py"):
            continue
        try:
            ast.parse(content, filename=path)
        except SyntaxError as e:
            issues.append(CheckIssue(
                severity=CheckSeverity.ERROR,
                code=CheckCode.SYNTAX_ERROR,
                path=path,
                message=f"Python syntax error at line {e.lineno}: {e.msg}",
                hint="Fix the syntax error before proceeding.",
            ))

    return issues


# ============================================================
# 辅助
# ============================================================


def _check_duplicates(
    content: str,
    modules: list[str],
    code: CheckCode,
    label: str,
    issues: list[CheckIssue],
) -> None:
    """检查重复注册"""
    for module in modules:
        pattern = module.replace("-", "_")
        count = content.count(pattern)
        if count > 1:
            issues.append(CheckIssue(
                severity=CheckSeverity.WARNING,
                code=code,
                path="",
                message=f"Module '{module}' appears {count} times in {label} file (possible duplicate).",
                hint=f"Check for duplicate {label} registrations of '{module}'.",
            ))


# ============================================================
# 综合自检
# ============================================================


def run_self_check(
    generated_modules: list[str],
    *,
    router_content: str = "",
    export_content: str = "",
    backend_router_content: str = "",
    python_files: dict[str, str] | None = None,
) -> SelfCheckResult:
    """执行综合自检

    Args:
        generated_modules: 已生成的模块名列表
        router_content: 前端 router 文件内容
        export_content: 前端 API 聚合导出内容
        backend_router_content: 后端 router init 内容
        python_files: Python 文件 {path: content}

    Returns:
        SelfCheckResult
    """
    all_issues: list[CheckIssue] = []
    checks_run = 0

    if router_content:
        all_issues.extend(check_frontend_routes(generated_modules, router_content))
        checks_run += 1

    if export_content:
        all_issues.extend(check_frontend_exports(generated_modules, export_content))
        checks_run += 1

    if backend_router_content:
        all_issues.extend(check_backend_routes(generated_modules, backend_router_content))
        checks_run += 1

    if python_files:
        all_issues.extend(check_python_syntax(python_files))
        checks_run += 1

    error_count = sum(1 for i in all_issues if i.severity == CheckSeverity.ERROR)
    warning_count = sum(1 for i in all_issues if i.severity == CheckSeverity.WARNING)

    return SelfCheckResult(
        passed=error_count == 0,
        issues=all_issues,
        checks_run=checks_run,
        error_count=error_count,
        warning_count=warning_count,
    )


__all__ = [
    "CheckCode",
    "CheckIssue",
    "CheckSeverity",
    "SelfCheckResult",
    "check_backend_routes",
    "check_frontend_exports",
    "check_frontend_routes",
    "check_python_syntax",
    "run_self_check",
]
