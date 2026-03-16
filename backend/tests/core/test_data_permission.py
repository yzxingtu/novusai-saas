"""
DataPermissionFilter 单元测试 / Data permission filter unit tests.

覆盖：ALL / SELF_ONLY / DEPT / CUSTOM 各 DataScope、缺 created_by/dept_id 时安全降级（where false）。
"""

from __future__ import annotations

from contextvars import copy_context

import pytest
from sqlalchemy import Column, Integer, select

from app.core.base_model import Base
from app.core.data_permission import DataPermissionFilter, data_permission_ctx
from app.enums.role import DataScope


# 测试用 Model：有 created_by、dept_id
class _ModelWithFields(Base):
    __tablename__ = "_test_model_full"
    id = Column(Integer, primary_key=True)
    created_by = Column(Integer, nullable=True)
    dept_id = Column(Integer, nullable=True)


# 测试用 Model：无 created_by / dept_id
class _ModelWithoutFields(Base):
    __tablename__ = "_test_model_minimal"
    id = Column(Integer, primary_key=True)


def _run_with_ctx(ctx_dict: dict, fn):
    """在指定 data_permission_ctx 下执行函数 / Run fn with data_permission_ctx set."""
    def run():
        token = data_permission_ctx.set(ctx_dict)
        try:
            return fn()
        finally:
            data_permission_ctx.reset(token)
    return copy_context().run(run)


class TestDataPermissionFilterAll:
    """ALL 范围：不添加过滤条件 / ALL scope: no filter."""

    def test_all_returns_query_unchanged(self):
        """ALL 时原样返回 query / ALL scope returns query unchanged."""
        q = select(_ModelWithFields.id)
        ctx = {"max_data_scope": DataScope.ALL.value}
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1))
        assert result is not None
        # ALL 不添加 where，编译后无 extra where
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "created_by" not in compiled
        assert "dept_id" not in compiled


class TestDataPermissionFilterSelfOnly:
    """SELF_ONLY 范围 / SELF_ONLY scope."""

    def test_self_only_adds_created_by_filter(self):
        """SELF_ONLY 添加 created_by = current_user_id / SELF_ONLY adds created_by filter."""
        q = select(_ModelWithFields.id)
        ctx = {"max_data_scope": DataScope.SELF_ONLY.value}
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, 42))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "created_by" in compiled
        assert "42" in compiled

    def test_self_only_no_created_by_returns_false(self):
        """Model 无 created_by 时返回 where(false()) 安全降级 / No created_by => where(false())."""
        q = select(_ModelWithoutFields.id)
        ctx = {"max_data_scope": DataScope.SELF_ONLY.value}
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithoutFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "1 = 0" in compiled or "false" in compiled.lower()

    def test_self_only_none_user_id_returns_false(self):
        """current_user_id 为 None 时返回 where(false()) / None current_user_id => where(false())."""
        q = select(_ModelWithFields.id)
        ctx = {"max_data_scope": DataScope.SELF_ONLY.value}
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, None))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "1 = 0" in compiled or "false" in compiled.lower()


class TestDataPermissionFilterDept:
    """DEPT_ONLY / DEPT_AND_CHILDREN 范围 / Dept scope."""

    def test_dept_only_adds_dept_id_in_filter(self):
        """部门范围添加 dept_id IN (...) / Dept scope adds dept_id IN filter."""
        q = select(_ModelWithFields.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "all_visible_dept_ids": [1, 2, 3],
        }
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "dept_id" in compiled
        assert "1" in compiled or "2" in compiled or "3" in compiled

    def test_dept_model_without_dept_id_returns_false(self):
        """Model 无 dept_id 时返回 where(false()) / No dept_id => where(false())."""
        q = select(_ModelWithoutFields.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "all_visible_dept_ids": [1],
        }
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithoutFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "1 = 0" in compiled or "false" in compiled.lower()

    def test_dept_empty_visible_dept_ids_returns_false(self):
        """all_visible_dept_ids 为空时返回 where(false()) / Empty dept ids => where(false())."""
        q = select(_ModelWithFields.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "all_visible_dept_ids": [],
        }
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "1 = 0" in compiled or "false" in compiled.lower()


class TestDataPermissionFilterCustom:
    """CUSTOM 范围 / CUSTOM scope."""

    def test_custom_adds_dept_id_in_filter(self):
        """CUSTOM 添加 dept_id IN custom_dept_ids / CUSTOM adds dept_id IN filter."""
        q = select(_ModelWithFields.id)
        ctx = {
            "max_data_scope": DataScope.CUSTOM.value,
            "custom_dept_ids": [5, 6],
        }
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "dept_id" in compiled

    def test_custom_empty_custom_dept_ids_returns_false(self):
        """custom_dept_ids 为空时返回 where(false()) / Empty custom_dept_ids => where(false())."""
        q = select(_ModelWithFields.id)
        ctx = {
            "max_data_scope": DataScope.CUSTOM.value,
            "custom_dept_ids": [],
        }
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "1 = 0" in compiled or "false" in compiled.lower()

    def test_custom_model_without_dept_id_returns_false(self):
        """Model 无 dept_id 时返回 where(false()) / No dept_id in CUSTOM => where(false())."""
        q = select(_ModelWithoutFields.id)
        ctx = {
            "max_data_scope": DataScope.CUSTOM.value,
            "custom_dept_ids": [1],
        }
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithoutFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "1 = 0" in compiled or "false" in compiled.lower()


class TestDataPermissionFilterCtxEmpty:
    """ctx 为空或默认时的回退行为 / Empty ctx fallback."""

    def test_empty_ctx_defaults_to_all(self):
        """ctx 为空时相当于 ALL，不添加过滤 / Empty ctx behaves like ALL."""
        q = select(_ModelWithFields.id)
        ctx = {}
        result = _run_with_ctx(ctx, lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1))
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "created_by" not in compiled
        assert "dept_id" not in compiled
