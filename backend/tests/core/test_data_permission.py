"""
DataPermissionFilter 单元测试 / Data permission filter unit tests.

覆盖：
- ALL / SELF_ONLY / DEPT / CUSTOM 各 DataScope
- org_node_id / dept_id 直接过滤
- created_by 回退到创建人组织
- 自定义创建人字段与创建人类型字段
- 创建时上下文字段自动补全
"""

from __future__ import annotations

from contextvars import copy_context

from sqlalchemy import Column, Integer, String, select

from app.core.base_model import Base
from app.core.data_permission import (
    DataPermissionFilter,
    data_permission_ctx,
    enrich_create_data_with_data_permission,
)
from app.enums.role import DataScope


class _ModelWithFields(Base):
    __tablename__ = "_test_model_full"

    id = Column(Integer, primary_key=True)
    created_by = Column(Integer, nullable=True)
    dept_id = Column(Integer, nullable=True)


class _ModelWithOrgNode(Base):
    __tablename__ = "_test_model_org"

    id = Column(Integer, primary_key=True)
    org_node_id = Column(Integer, nullable=True)


class _ModelWithoutFields(Base):
    __tablename__ = "_test_model_minimal"

    id = Column(Integer, primary_key=True)


class _ModelWithCustomCreator(Base):
    __tablename__ = "_test_model_custom_creator"

    __data_permission__ = True
    __data_permission_creator_field__ = "initiated_by"
    __data_permission_creator_scope__ = "tenant_admin"

    id = Column(Integer, primary_key=True)
    initiated_by = Column(Integer, nullable=True)


class _ModelWithCreatorScopeField(Base):
    __tablename__ = "_test_model_creator_scope_field"

    __data_permission__ = True
    __data_permission_creator_field__ = "initiated_by"
    __data_permission_creator_scope_field__ = "started_by_type"
    __data_permission_creator_scopes__ = ["tenant_admin"]

    id = Column(Integer, primary_key=True)
    initiated_by = Column(Integer, nullable=True)
    started_by_type = Column(String(32), nullable=True)


class _ParentScopedModel(Base):
    __tablename__ = "_test_parent_scoped"

    __data_permission__ = True
    __data_permission_creator_scope__ = "tenant_admin"

    id = Column(Integer, primary_key=True)
    created_by = Column(Integer, nullable=True)
    tenant_id = Column(Integer, nullable=True)


class _ChildInheritedModel(Base):
    __tablename__ = "_test_child_inherited"

    __data_permission__ = True
    __data_permission_creator_scope__ = "tenant_admin"
    __data_permission_parent_model__ = _ParentScopedModel
    __data_permission_parent_key__ = "parent_id"

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, nullable=True)


class _AdminScopedModel(Base):
    __tablename__ = "_test_admin_scoped"

    __data_permission__ = True
    __data_permission_creator_scope__ = "admin"

    id = Column(Integer, primary_key=True)
    created_by = Column(Integer, nullable=True)


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
    def test_all_returns_query_unchanged(self):
        q = select(_ModelWithFields.id)
        ctx = {"max_data_scope": DataScope.ALL.value}
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "created_by" not in compiled
        assert "dept_id" not in compiled


class TestDataPermissionFilterSelfOnly:
    def test_self_only_adds_created_by_filter(self):
        q = select(_ModelWithFields.id)
        ctx = {"max_data_scope": DataScope.SELF_ONLY.value}
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithFields, 42),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "created_by" in compiled
        assert "42" in compiled

    def test_self_only_custom_creator_scope_field_adds_both_filters(self):
        q = select(_ModelWithCreatorScopeField.id)
        ctx = {
            "max_data_scope": DataScope.SELF_ONLY.value,
            "current_user_scope": "tenant_admin",
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithCreatorScopeField, 9),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "initiated_by" in compiled
        assert "started_by_type" in compiled
        assert "tenant_admin" in compiled

    def test_self_only_inherited_parent_scope_uses_parent_subquery(self):
        q = select(_ChildInheritedModel.id)
        ctx = {
            "max_data_scope": DataScope.SELF_ONLY.value,
            "current_user_id": 9,
            "current_user_scope": "tenant_admin",
            "current_tenant_id": 2,
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ChildInheritedModel, 9),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "_test_child_inherited.parent_id IN (SELECT _test_parent_scoped.id" in compiled
        assert "_test_parent_scoped.created_by = 9" in compiled
        assert "_test_parent_scoped.tenant_id = 2" in compiled

    def test_self_only_no_owner_field_returns_false(self):
        q = select(_ModelWithoutFields.id)
        ctx = {"max_data_scope": DataScope.SELF_ONLY.value}
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithoutFields, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert compiled == str(q.compile(compile_kwargs={"literal_binds": True}))
        assert DataPermissionFilter.is_enabled(_ModelWithoutFields) is False


class TestDataPermissionFilterDept:
    def test_dept_only_adds_dept_id_in_filter(self):
        q = select(_ModelWithFields.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "all_visible_dept_ids": [1, 2, 3],
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "dept_id" in compiled
        assert "IN (1, 2, 3)" in compiled

    def test_dept_only_adds_org_node_id_filter(self):
        q = select(_ModelWithOrgNode.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "effective_scope_org_ids": [8, 9],
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithOrgNode, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "org_node_id" in compiled
        assert "IN (8, 9)" in compiled

    def test_dept_only_custom_creator_falls_back_to_tenant_admin_subquery(self):
        q = select(_ModelWithCustomCreator.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "effective_scope_org_ids": [11, 12],
            "current_tenant_id": 3,
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithCustomCreator, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "initiated_by" in compiled
        assert "tenant_admins" in compiled
        assert "tenant_admins.org_node_id IN (11, 12)" in compiled
        assert "tenant_admins.tenant_id = 3" in compiled

    def test_dept_only_creator_scope_field_builds_scope_predicate(self):
        q = select(_ModelWithCreatorScopeField.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "effective_scope_org_ids": [21],
            "current_tenant_id": 7,
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithCreatorScopeField, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "started_by_type = 'tenant_admin'" in compiled
        assert "tenant_admins.org_node_id IN (21)" in compiled

    def test_dept_only_parent_scope_inherits_creator_org_filter(self):
        q = select(_ChildInheritedModel.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "effective_scope_org_ids": [21],
            "current_user_scope": "tenant_admin",
            "current_tenant_id": 7,
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ChildInheritedModel, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "_test_child_inherited.parent_id IN (SELECT _test_parent_scoped.id" in compiled
        assert "tenant_admins.org_node_id IN (21)" in compiled
        assert "_test_parent_scoped.tenant_id = 7" in compiled

    def test_dept_model_without_supported_fields_returns_false(self):
        q = select(_ModelWithoutFields.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "all_visible_dept_ids": [1],
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithoutFields, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert compiled == str(q.compile(compile_kwargs={"literal_binds": True}))
        assert DataPermissionFilter.is_enabled(_ModelWithoutFields) is False


class TestDataPermissionFilterCustom:
    def test_custom_uses_custom_dept_ids(self):
        q = select(_ModelWithFields.id)
        ctx = {
            "max_data_scope": DataScope.CUSTOM.value,
            "custom_dept_ids": [5, 6],
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithFields, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "dept_id" in compiled
        assert "IN (5, 6)" in compiled

    def test_custom_creator_falls_back_to_visible_org_ids_when_custom_empty(self):
        q = select(_ModelWithCustomCreator.id)
        ctx = {
            "max_data_scope": DataScope.CUSTOM.value,
            "custom_org_ids": [],
            "effective_scope_org_ids": [31],
            "current_tenant_id": 9,
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithCustomCreator, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert "tenant_admins.org_node_id IN (31)" in compiled


class TestDataPermissionScopeCompatibility:
    def test_explicit_admin_scope_is_skipped_for_tenant_admin_context(self):
        q = select(_AdminScopedModel.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "effective_scope_org_ids": [99],
            "current_user_scope": "tenant_admin",
            "current_tenant_id": 1,
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _AdminScopedModel, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert compiled == str(q.compile(compile_kwargs={"literal_binds": True}))

    def test_creator_scope_field_model_is_skipped_when_current_scope_not_supported(self):
        q = select(_ModelWithCreatorScopeField.id)
        ctx = {
            "max_data_scope": DataScope.DEPT_ONLY.value,
            "effective_scope_org_ids": [55],
            "current_user_scope": "admin",
        }
        result = _run_with_ctx(
            ctx,
            lambda: DataPermissionFilter.apply(q, _ModelWithCreatorScopeField, 1),
        )
        compiled = str(result.compile(compile_kwargs={"literal_binds": True}))
        assert compiled == str(q.compile(compile_kwargs={"literal_binds": True}))


class TestCreateDataEnrichment:
    def test_enrich_create_data_populates_default_fields(self):
        ctx = {
            "current_user_id": 15,
            "primary_org_id": 88,
            "primary_department_id": 88,
        }
        enriched = _run_with_ctx(
            ctx,
            lambda: enrich_create_data_with_data_permission(_ModelWithFields, {}),
        )
        assert enriched["created_by"] == 15
        assert enriched["dept_id"] == 88

    def test_enrich_create_data_respects_custom_creator_and_scope_field(self):
        ctx = {
            "current_user_id": 23,
            "current_user_scope": "tenant_admin",
        }
        enriched = _run_with_ctx(
            ctx,
            lambda: enrich_create_data_with_data_permission(_ModelWithCreatorScopeField, {}),
        )
        assert enriched["initiated_by"] == 23
        assert enriched["started_by_type"] == "tenant_admin"
