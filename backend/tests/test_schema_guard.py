"""
Schema Guard — 单元测试

覆盖：
- 未知字段检测 (extra_field)
- 缺失必填字段 (missing_field)
- 类型错误 (type_error)
- 有效输入通过
- fix_suggestions 生成
- to_tool_output 序列化
- guard_merge_patch / guard_crud_config
"""

import pytest

from app.codegen.schema_guard import (
    SCHEMA_VERSION,
    GuardErrorType,
    GuardResult,
    InvalidField,
    guard_batch_project,
    guard_crud_config,
    guard_merge_patch,
)


# ============================================================
# 辅助
# ============================================================


def _minimal_entity() -> dict:
    """最小可用实体配置"""
    return {
        "module": "order",
        "table_name": "orders",
        "display_name": "订单",
        "display_name_en": "Order",
        "parent_menu": "trade",
        "fields": [
            {
                "name": "title",
                "type": "string",
                "label": "标题",
                "label_zh": "标题",
                "label_en": "Title",
            },
        ],
    }


def _minimal_project() -> dict:
    """最小可用 BatchCrudProject"""
    return {
        "project_name": "test_project",
        "entities": [_minimal_entity()],
    }


# ============================================================
# guard_batch_project
# ============================================================


class TestGuardBatchProject:
    """BatchCrudProject schema guard"""

    def test_valid_project_passes(self):
        """有效项目通过"""
        r = guard_batch_project(_minimal_project())
        assert r.valid is True
        assert len(r.invalid_fields) == 0

    def test_extra_field_detected(self):
        """未知字段被检测"""
        data = _minimal_project()
        data["hallucination_field"] = "bad"
        data["another_fake"] = 123

        r = guard_batch_project(data)
        assert r.valid is False
        assert r.error_code == "SCHEMA_GUARD_FAILED"

        extra_fields = [
            f for f in r.invalid_fields
            if f.error_type == GuardErrorType.EXTRA_FIELD
        ]
        assert len(extra_fields) == 2
        paths = {f.path for f in extra_fields}
        assert "hallucination_field" in paths
        assert "another_fake" in paths

    def test_missing_required_field(self):
        """缺失必填字段"""
        r = guard_batch_project({})
        assert r.valid is False

        missing = [
            f for f in r.invalid_fields
            if f.error_type == GuardErrorType.MISSING_FIELD
        ]
        assert len(missing) > 0

    def test_type_error(self):
        """类型错误"""
        data = _minimal_project()
        data["entities"] = "not_a_list"

        r = guard_batch_project(data)
        assert r.valid is False

        type_errors = [
            f for f in r.invalid_fields
            if f.error_type == GuardErrorType.TYPE_ERROR
        ]
        assert len(type_errors) > 0

    def test_empty_entities_rejected(self):
        """空 entities 列表被拒绝"""
        data = {"project_name": "test", "entities": []}
        r = guard_batch_project(data)
        assert r.valid is False

    def test_multiple_error_types(self):
        """同时存在多种错误"""
        data = {
            "fake_field": "extra",
            # missing: project_name, entities
        }
        r = guard_batch_project(data)
        assert r.valid is False

        error_types = {f.error_type for f in r.invalid_fields}
        assert GuardErrorType.EXTRA_FIELD in error_types

    def test_schema_version_present(self):
        """结果包含 schema_version"""
        r = guard_batch_project(_minimal_project())
        assert r.schema_version == SCHEMA_VERSION


# ============================================================
# guard_merge_patch
# ============================================================


class TestGuardMergePatch:
    """BatchMergePatch schema guard"""

    def test_valid_patch_passes(self):
        """有效 patch 通过"""
        r = guard_merge_patch({})
        assert r.valid is True

    def test_extra_field_in_patch(self):
        """patch 中的未知字段"""
        r = guard_merge_patch({"unknown_key": "value"})
        assert r.valid is False
        extra = [
            f for f in r.invalid_fields
            if f.error_type == GuardErrorType.EXTRA_FIELD
        ]
        assert len(extra) == 1
        assert extra[0].path == "unknown_key"

    def test_valid_patch_with_entities(self):
        """带实体的 patch 通过"""
        r = guard_merge_patch({
            "entities": [_minimal_entity()],
        })
        assert r.valid is True


# ============================================================
# guard_crud_config
# ============================================================


class TestGuardCrudConfig:
    """CrudConfig schema guard"""

    def test_valid_config_passes(self):
        """有效 config 通过"""
        r = guard_crud_config(_minimal_entity())
        assert r.valid is True

    def test_missing_required(self):
        """缺失必填字段"""
        r = guard_crud_config({})
        assert r.valid is False

    def test_extra_field_in_config(self):
        """config 中的未知字段"""
        data = _minimal_entity()
        data["ai_hallucination"] = True
        r = guard_crud_config(data)
        assert r.valid is False
        extra = [
            f for f in r.invalid_fields
            if f.error_type == GuardErrorType.EXTRA_FIELD
        ]
        assert len(extra) >= 1


# ============================================================
# fix_suggestions
# ============================================================


class TestFixSuggestions:
    """修复建议生成"""

    def test_extra_field_suggestion(self):
        """未知字段的修复建议"""
        data = _minimal_project()
        data["bad_field"] = "x"
        r = guard_batch_project(data)
        assert any("Remove" in s for s in r.fix_suggestions)

    def test_missing_field_suggestion(self):
        """缺失字段的修复建议"""
        r = guard_batch_project({})
        assert any("Add" in s or "required" in s for s in r.fix_suggestions)


# ============================================================
# to_tool_output
# ============================================================


class TestToToolOutput:
    """工具输出序列化"""

    def test_output_format(self):
        """to_tool_output 格式正确"""
        data = _minimal_project()
        data["bad"] = True
        r = guard_batch_project(data)
        output = r.to_tool_output()

        assert output["success"] is False
        assert output["error_code"] == "SCHEMA_GUARD_FAILED"
        assert isinstance(output["invalid_fields"], list)
        assert isinstance(output["fix_suggestions"], list)
        assert output["schema_version"] == SCHEMA_VERSION

    def test_valid_result_not_serialized_as_error(self):
        """有效结果不应通过 to_tool_output"""
        r = guard_batch_project(_minimal_project())
        assert r.valid is True
        # to_tool_output 仍可调用但 success=False（设计为仅错误时使用）
        output = r.to_tool_output()
        assert output["success"] is False  # 始终 False，仅在 guard 失败时才调用
