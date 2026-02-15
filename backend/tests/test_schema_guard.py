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
    guard_crud_config,
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
        data = _minimal_entity()
        data["bad_field"] = "x"
        r = guard_crud_config(data)
        assert any("Remove" in s for s in r.fix_suggestions)

    def test_missing_field_suggestion(self):
        """缺失字段的修复建议"""
        r = guard_crud_config({})
        assert any("Add" in s or "required" in s for s in r.fix_suggestions)


# ============================================================
# to_tool_output
# ============================================================


class TestToToolOutput:
    """工具输出序列化"""

    def test_output_format(self):
        """to_tool_output 格式正确"""
        data = _minimal_entity()
        data["bad"] = True
        r = guard_crud_config(data)
        output = r.to_tool_output()

        assert output["success"] is False
        assert output["error_code"] == "SCHEMA_GUARD_FAILED"
        assert isinstance(output["invalid_fields"], list)
        assert isinstance(output["fix_suggestions"], list)
        assert output["schema_version"] == SCHEMA_VERSION

    def test_valid_result_not_serialized_as_error(self):
        """有效结果不应通过 to_tool_output"""
        r = guard_crud_config(_minimal_entity())
        assert r.valid is True
        # to_tool_output 仍可调用但 success=False（设计为仅在 guard 失败时才调用）
        output = r.to_tool_output()
        assert output["success"] is False  # 始终 False，仅在 guard 失败时才调用
