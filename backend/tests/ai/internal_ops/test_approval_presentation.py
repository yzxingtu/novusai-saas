"""
Issue #46: 基于 RBAC 生成 AI 内部工具操作确认展示数据
Test type: behavioral
Scope: build_approval_presentation, sensitive filtering, risk heuristics,
       title fallback chain, technical detail inclusion.
Real dependencies: build_approval_presentation, ToolApprovalPresentation.
Mocked dependencies: AsyncSession via AsyncMock.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.internal_ops.approval_presentation import (
    ApprovalDetail,
    ToolApprovalPresentation,
    _extract_safe_details,
    _format_detail_value,
    _infer_risk_level,
    _is_sensitive_key,
    build_approval_presentation,
)


# ---------------------------------------------------------------------------
# Sensitive key filtering / 敏感字段过滤
# ---------------------------------------------------------------------------


class TestSensitiveKeyFiltering:
    @pytest.mark.parametrize(
        "key",
        [
            "password",
            "old_password",
            "new_password",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "secret",
            "secret_key",
            "authorization",
            "cookie",
            "headers",
            "private_key",
            "credential",
        ],
    )
    def test_sensitive_keys_detected(self, key: str) -> None:
        assert _is_sensitive_key(key) is True

    @pytest.mark.parametrize(
        "key",
        ["name", "price", "billing_cycle", "status", "tenant_id", "email"],
    )
    def test_safe_keys_pass(self, key: str) -> None:
        assert _is_sensitive_key(key) is False

    def test_mixed_case_and_underscore_variants(self) -> None:
        assert _is_sensitive_key("API_KEY") is True
        assert _is_sensitive_key("Access-Token") is True
        assert _is_sensitive_key("SECRET") is True


# ---------------------------------------------------------------------------
# Risk level heuristics / 风险等级
# ---------------------------------------------------------------------------


class TestRiskLevel:
    def test_delete_is_high_risk(self) -> None:
        assert _infer_risk_level("DELETE", "delete") == "high"

    def test_disable_is_high_risk(self) -> None:
        assert _infer_risk_level("POST", "disable") == "high"

    def test_post_is_medium_risk(self) -> None:
        assert _infer_risk_level("POST", "create") == "medium"

    def test_patch_is_medium_risk(self) -> None:
        assert _infer_risk_level("PATCH", "update") == "medium"

    def test_get_is_low_risk(self) -> None:
        assert _infer_risk_level("GET", "read") == "low"


# ---------------------------------------------------------------------------
# Safe detail extraction / 安全详情提取
# ---------------------------------------------------------------------------


class TestExtractSafeDetails:
    def test_body_fields_extracted(self) -> None:
        body = {"name": "Pro Plan", "price": 99, "billing_cycle": "monthly"}
        details = _extract_safe_details(
            body=body, path_params={}, query_params={}
        )
        labels = [d.label for d in details]
        assert "name" in labels
        assert "price" in labels
        assert "billing_cycle" in labels

    def test_sensitive_body_fields_excluded(self) -> None:
        body = {
            "name": "Pro Plan",
            "password": "hunter2",
            "api_key": "sk-123",
            "token": "abc",
            "authorization": "Bearer xxx",
        }
        details = _extract_safe_details(
            body=body, path_params={}, query_params={}
        )
        labels = [d.label for d in details]
        assert "name" in labels
        assert "password" not in labels
        assert "api_key" not in labels
        assert "token" not in labels
        assert "authorization" not in labels

    def test_path_params_included(self) -> None:
        details = _extract_safe_details(
            body=None,
            path_params={"tenant_id": 42},
            query_params={},
        )
        assert any(d.label == "tenant_id" and d.value == "42" for d in details)

    def test_none_values_skipped(self) -> None:
        body = {"name": "test", "description": None}
        details = _extract_safe_details(
            body=body, path_params={}, query_params={}
        )
        assert len(details) == 1
        assert details[0].label == "name"

    def test_max_fields_limit(self) -> None:
        body = {f"field_{i}": f"val_{i}" for i in range(20)}
        details = _extract_safe_details(
            body=body, path_params={}, query_params={}, max_fields=5
        )
        assert len(details) == 5


# ---------------------------------------------------------------------------
# Value formatting / 值格式化
# ---------------------------------------------------------------------------


class TestFormatDetailValue:
    def test_bool_true(self) -> None:
        assert _format_detail_value(True) == "是"

    def test_bool_false(self) -> None:
        assert _format_detail_value(False) == "否"

    def test_int(self) -> None:
        assert _format_detail_value(42) == "42"

    def test_string(self) -> None:
        assert _format_detail_value("hello") == "hello"

    def test_none_returns_empty(self) -> None:
        assert _format_detail_value(None) == ""

    def test_dict_returns_empty(self) -> None:
        assert _format_detail_value({"a": 1}) == ""

    def test_long_string_returns_empty(self) -> None:
        assert _format_detail_value("x" * 300) == ""


# ---------------------------------------------------------------------------
# build_approval_presentation (async) / 异步构建函数
# ---------------------------------------------------------------------------


def _make_mock_db(
    *,
    permission: SimpleNamespace | None = None,
    parent_menu: SimpleNamespace | None = None,
) -> AsyncMock:
    """Build a mock AsyncSession that returns the given permission chain."""
    db = AsyncMock()

    if permission is None:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute.return_value = result
        return db

    # First call: find permission by code
    perm_result = MagicMock()
    perm_result.scalar_one_or_none.return_value = permission

    if parent_menu is not None:
        # Second call: find parent menu
        parent_result = MagicMock()
        parent_result.scalar_one_or_none.return_value = parent_menu
        db.execute.side_effect = [perm_result, parent_result]
    else:
        # Permission has no parent
        no_parent_result = MagicMock()
        no_parent_result.scalar_one_or_none.return_value = None
        db.execute.side_effect = [perm_result, no_parent_result]

    return db


@pytest.mark.asyncio
async def test_build_presentation_with_permission_and_menu() -> None:
    """Permission found + parent menu → title includes action + menu label."""
    permission = SimpleNamespace(
        id=100,
        code="tenant_plan:create",
        name="tenant.plan.create",
        type="operation",
        parent_id=50,
    )
    parent_menu = SimpleNamespace(
        id=50,
        code="menu:tenant.plan",
        name="tenant.plan.title",
        type="menu",
        parent_id=None,
    )
    db = _make_mock_db(permission=permission, parent_menu=parent_menu)

    presentation = await build_approval_presentation(
        db=db,
        operation_id="POST:/admin/plans",
        method="POST",
        path="/admin/plans",
        permission_code="tenant_plan:create",
        summary="Create a tenant plan",
        action="create",
        body={"name": "Pro", "price": 99, "billing_cycle": "monthly"},
        path_params={},
        query_params={},
    )

    assert isinstance(presentation, ToolApprovalPresentation)
    assert presentation.risk_level == "medium"
    assert presentation.permission_code == "tenant_plan:create"
    assert presentation.operation_type == "POST"
    # Technical details always present
    assert presentation.technical["operation_id"] == "POST:/admin/plans"
    assert presentation.technical["method"] == "POST"
    # Safe business details extracted
    labels = [d.label for d in presentation.details]
    assert "name" in labels
    assert "price" in labels


@pytest.mark.asyncio
async def test_build_presentation_permission_not_found_fallback() -> None:
    """Permission not found → fallback to summary or method+path+code."""
    db = _make_mock_db(permission=None)

    presentation = await build_approval_presentation(
        db=db,
        operation_id="POST:/admin/unknown",
        method="POST",
        path="/admin/unknown",
        permission_code="unknown:action",
        summary="Some operation summary",
        action="action",
        body={"name": "test"},
        path_params={},
        query_params={},
    )

    assert isinstance(presentation, ToolApprovalPresentation)
    # Title should fall back to summary
    assert presentation.title == "Some operation summary"
    assert presentation.permission_code == "unknown:action"
    assert presentation.menu_label is None
    # Technical details still present
    assert presentation.technical["permission_code"] == "unknown:action"


@pytest.mark.asyncio
async def test_build_presentation_no_db() -> None:
    """db=None → no crash, pure fallback behavior."""
    presentation = await build_approval_presentation(
        db=None,
        operation_id="DELETE:/admin/tenants/{tenant_id}",
        method="DELETE",
        path="/admin/tenants/{tenant_id}",
        permission_code="tenant:delete",
        summary="Delete a tenant",
        action="delete",
        body=None,
        path_params={"tenant_id": 5},
        query_params={},
    )

    assert isinstance(presentation, ToolApprovalPresentation)
    assert presentation.risk_level == "high"
    assert presentation.title == "Delete a tenant"
    # target inferred from path_params
    assert presentation.target is not None
    assert presentation.target.type == "tenant"
    assert presentation.target.name == "5"


@pytest.mark.asyncio
async def test_build_presentation_sensitive_fields_not_in_output() -> None:
    """password, token, api_key etc must NOT appear in details or to_dict()."""
    db = _make_mock_db(permission=None)

    presentation = await build_approval_presentation(
        db=db,
        operation_id="POST:/admin/users",
        method="POST",
        path="/admin/users",
        permission_code="user:create",
        summary="Create user",
        action="create",
        body={
            "name": "Alice",
            "email": "alice@example.com",
            "password": "super_secret_123",
            "api_key": "sk-abc123",
            "token": "eyJ...",
            "authorization": "Bearer xyz",
            "cookie": "session=abc",
            "headers": {"X-Custom": "val"},
        },
        path_params={},
        query_params={},
    )

    output = presentation.to_dict()
    output_str = str(output)
    # Sensitive values must not leak
    assert "super_secret_123" not in output_str
    assert "sk-abc123" not in output_str
    assert "eyJ..." not in output_str
    # Safe fields present
    labels = [d["label"] for d in output.get("details", [])]
    assert "name" in labels
    assert "email" in labels
    assert "password" not in labels


@pytest.mark.asyncio
async def test_build_presentation_db_error_graceful() -> None:
    """DB query failure → graceful degradation, no crash."""
    db = AsyncMock()
    db.execute.side_effect = RuntimeError("connection lost")

    presentation = await build_approval_presentation(
        db=db,
        operation_id="POST:/admin/plans",
        method="POST",
        path="/admin/plans",
        permission_code="tenant_plan:create",
        summary="Create plan",
        action="create",
        body={"name": "Basic"},
        path_params={},
        query_params={},
    )

    assert isinstance(presentation, ToolApprovalPresentation)
    # Fallback title should be summary
    assert presentation.title == "Create plan"
    assert presentation.menu_label is None


# ---------------------------------------------------------------------------
# ToolApprovalPresentation.to_dict() / 序列化
# ---------------------------------------------------------------------------


class TestToDict:
    def test_none_fields_excluded(self) -> None:
        p = ToolApprovalPresentation(title="Test", summary=None, menu_label=None)
        d = p.to_dict()
        assert "summary" not in d
        assert "menu_label" not in d
        assert d["title"] == "Test"

    def test_empty_details_excluded(self) -> None:
        p = ToolApprovalPresentation(title="Test", details=[])
        d = p.to_dict()
        assert "details" not in d

    def test_technical_included(self) -> None:
        p = ToolApprovalPresentation(
            title="Test",
            technical={"operation_id": "POST:/admin/x"},
        )
        d = p.to_dict()
        assert d["technical"]["operation_id"] == "POST:/admin/x"
