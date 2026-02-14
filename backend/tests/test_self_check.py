"""
生成后自检 — 单元测试

覆盖：
- 前端路由缺失/重复
- 前端 API export 缺失/重复
- 后端路由缺失
- Python 语法错误
- 综合自检（通过/失败）
- 序列化
"""

import pytest

from app.codegen.self_check import (
    CheckCode,
    CheckSeverity,
    SelfCheckResult,
    check_backend_routes,
    check_frontend_exports,
    check_frontend_routes,
    check_python_syntax,
    run_self_check,
)


# ============================================================
# 前端路由
# ============================================================


class TestFrontendRoutes:
    """前端路由检查"""

    def test_route_missing(self):
        issues = check_frontend_routes(
            ["order", "product"],
            "import order from './order'",
        )
        missing = [i for i in issues if i.code == CheckCode.ROUTE_MISSING]
        assert len(missing) == 1
        assert "product" in missing[0].message

    def test_route_present(self):
        issues = check_frontend_routes(
            ["order"],
            "import order from './order'\npath: '/order'",
        )
        missing = [i for i in issues if i.code == CheckCode.ROUTE_MISSING]
        assert len(missing) == 0

    def test_route_duplicate(self):
        issues = check_frontend_routes(
            ["order"],
            "import order\nimport order\npath order",
        )
        dupes = [i for i in issues if i.code == CheckCode.ROUTE_DUPLICATE]
        assert len(dupes) == 1

    def test_kebab_case_match(self):
        """kebab-case 模块名也能匹配"""
        issues = check_frontend_routes(
            ["order-item"],
            "import order_item from './order-item'",
        )
        missing = [i for i in issues if i.code == CheckCode.ROUTE_MISSING]
        assert len(missing) == 0


# ============================================================
# 前端 API Export
# ============================================================


class TestFrontendExports:
    """前端 API 导出检查"""

    def test_export_missing(self):
        issues = check_frontend_exports(
            ["order", "product"],
            "export * from './order'",
        )
        missing = [i for i in issues if i.code == CheckCode.EXPORT_MISSING]
        assert len(missing) == 1
        assert "product" in missing[0].message

    def test_export_present(self):
        issues = check_frontend_exports(
            ["order"],
            "export * from './order'",
        )
        missing = [i for i in issues if i.code == CheckCode.EXPORT_MISSING]
        assert len(missing) == 0

    def test_export_duplicate(self):
        issues = check_frontend_exports(
            ["order"],
            "export * from './order'\nexport * from './order'",
        )
        dupes = [i for i in issues if i.code == CheckCode.EXPORT_DUPLICATE]
        assert len(dupes) == 1


# ============================================================
# 后端路由
# ============================================================


class TestBackendRoutes:
    """后端路由检查"""

    def test_backend_route_missing(self):
        issues = check_backend_routes(
            ["order"],
            "from .product import router",
        )
        missing = [i for i in issues if i.code == CheckCode.BACKEND_ROUTE_MISSING]
        assert len(missing) == 1

    def test_backend_route_present(self):
        issues = check_backend_routes(
            ["order"],
            "from .order import router",
        )
        missing = [i for i in issues if i.code == CheckCode.BACKEND_ROUTE_MISSING]
        assert len(missing) == 0


# ============================================================
# Python 语法
# ============================================================


class TestPythonSyntax:
    """Python 语法检查"""

    def test_valid_python(self):
        issues = check_python_syntax({
            "model.py": "class Order:\n    pass\n",
        })
        assert len(issues) == 0

    def test_syntax_error(self):
        issues = check_python_syntax({
            "model.py": "class Order\n    pass\n",  # missing colon
        })
        assert len(issues) == 1
        assert issues[0].code == CheckCode.SYNTAX_ERROR
        assert "syntax" in issues[0].message.lower()

    def test_non_python_skipped(self):
        issues = check_python_syntax({
            "template.html": "<div>{{ invalid python",
        })
        assert len(issues) == 0

    def test_multiple_files(self):
        issues = check_python_syntax({
            "good.py": "x = 1\n",
            "bad.py": "def f(\n",
        })
        assert len(issues) == 1
        assert issues[0].path == "bad.py"


# ============================================================
# 综合自检
# ============================================================


class TestRunSelfCheck:
    """综合自检"""

    def test_all_pass(self):
        result = run_self_check(
            ["order"],
            router_content="import order from './order'",
            export_content="export * from './order'",
            backend_router_content="from .order import router",
            python_files={"order.py": "x = 1\n"},
        )
        assert result.passed is True
        assert result.error_count == 0
        assert result.checks_run == 4

    def test_route_failure(self):
        result = run_self_check(
            ["order", "product"],
            router_content="import order from './order'",
        )
        assert result.passed is False
        assert result.error_count >= 1

    def test_no_checks(self):
        """不提供任何内容时不执行检查"""
        result = run_self_check(["order"])
        assert result.passed is True
        assert result.checks_run == 0

    def test_mixed_issues(self):
        """同时有 error 和 warning"""
        result = run_self_check(
            ["order"],
            router_content="// no routes here",  # missing route → error
            export_content="// no exports here",  # missing export → warning
        )
        assert result.error_count >= 1
        assert result.warning_count >= 1
        assert result.passed is False


class TestSerialization:
    """序列化"""

    def test_to_tool_output(self):
        result = run_self_check(
            ["order"],
            router_content="import order",
        )
        output = result.to_tool_output()
        assert "passed" in output
        assert "issues" in output
        assert "checks_run" in output
