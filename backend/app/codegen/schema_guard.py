"""
AI Schema Guard — 严格校验 + 结构化回退

对 AI 输出的 CrudConfig 执行严格 schema 校验：
- extra=forbid: 未知字段直接报错，不静默丢弃
- 缺失必填字段：结构化报错
- 类型错误：结构化报错
- 返回 invalid_fields 列表 (path + reason)
- 提供修复建议供 AI 自动修复 loop 使用
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError


# ============================================================
# Schema 版本
# ============================================================

SCHEMA_VERSION = "2.6.0"


# ============================================================
# Guard 错误类型
# ============================================================


class GuardErrorType(str, Enum):
    """Guard 错误类型"""

    EXTRA_FIELD = "extra_field"
    MISSING_FIELD = "missing_field"
    TYPE_ERROR = "type_error"
    VALUE_ERROR = "value_error"
    VALIDATION_ERROR = "validation_error"


class InvalidField(BaseModel):
    """无效字段描述"""

    path: str = Field(..., description="Field path (dot notation)")
    reason: str = Field(..., description="Error reason")
    error_type: GuardErrorType = Field(..., description="Error classification")
    input_value: str = Field("", description="The invalid value (truncated)")


class GuardResult(BaseModel):
    """Schema Guard 结果"""

    valid: bool = Field(True)
    error_code: str = Field("", description="Error code for programmatic handling")
    message: str = Field("", description="Human-readable summary")
    invalid_fields: list[InvalidField] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(
        default_factory=list,
        description="Actionable fix suggestions for AI auto-fix loop",
    )
    schema_version: str = Field(SCHEMA_VERSION)

    def to_tool_output(self) -> dict[str, Any]:
        """Convert to tool output dict for AI consumption"""
        return {
            "success": False,
            "error_code": self.error_code,
            "message": self.message,
            "invalid_fields": [f.model_dump() for f in self.invalid_fields],
            "fix_suggestions": self.fix_suggestions,
            "schema_version": self.schema_version,
        }


# ============================================================
# Pydantic ValidationError 解析
# ============================================================


def _classify_error(error_type: str) -> GuardErrorType:
    """将 Pydantic error type 映射到 GuardErrorType"""
    if "extra" in error_type:
        return GuardErrorType.EXTRA_FIELD
    if "missing" in error_type:
        return GuardErrorType.MISSING_FIELD
    if "type" in error_type or "int_parsing" in error_type or "bool_parsing" in error_type:
        return GuardErrorType.TYPE_ERROR
    if "value" in error_type or "enum" in error_type:
        return GuardErrorType.VALUE_ERROR
    return GuardErrorType.VALIDATION_ERROR


def _truncate(value: Any, max_len: int = 100) -> str:
    """截断值的字符串表示"""
    s = str(value)
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def _parse_validation_error(exc: ValidationError) -> list[InvalidField]:
    """从 Pydantic ValidationError 提取 InvalidField 列表"""
    fields: list[InvalidField] = []
    for error in exc.errors():
        path = ".".join(str(loc) for loc in error.get("loc", []))
        error_type = error.get("type", "")
        msg = error.get("msg", "")
        input_val = error.get("input", "")

        fields.append(InvalidField(
            path=path,
            reason=msg,
            error_type=_classify_error(error_type),
            input_value=_truncate(input_val),
        ))
    return fields


def _generate_fix_suggestions(invalid_fields: list[InvalidField]) -> list[str]:
    """根据无效字段生成修复建议"""
    suggestions: list[str] = []
    extra_fields = [f for f in invalid_fields if f.error_type == GuardErrorType.EXTRA_FIELD]
    missing_fields = [f for f in invalid_fields if f.error_type == GuardErrorType.MISSING_FIELD]
    type_errors = [f for f in invalid_fields if f.error_type == GuardErrorType.TYPE_ERROR]

    if extra_fields:
        field_names = ", ".join(f.path for f in extra_fields)
        suggestions.append(
            f"Remove unknown fields: {field_names}. "
            f"Only use fields defined in the schema."
        )

    if missing_fields:
        field_names = ", ".join(f.path for f in missing_fields)
        suggestions.append(
            f"Add required fields: {field_names}."
        )

    if type_errors:
        for f in type_errors:
            suggestions.append(
                f"Fix type of '{f.path}': {f.reason}."
            )

    return suggestions


# ============================================================
# Guard 入口
# ============================================================


def guard_crud_config(raw_data: dict[str, Any]) -> GuardResult:
    """校验 CrudConfig 输入

    Args:
        raw_data: AI 输出的原始 dict

    Returns:
        GuardResult
    """
    from app.codegen.schemas import CrudConfig

    invalid_fields, _ = _validate_strict(CrudConfig, raw_data)

    if not invalid_fields:
        return GuardResult(valid=True)

    return GuardResult(
        valid=False,
        error_code="SCHEMA_GUARD_FAILED",
        message=(
            f"CrudConfig validation failed: "
            f"{len(invalid_fields)} field error(s)"
        ),
        invalid_fields=invalid_fields,
        fix_suggestions=_generate_fix_suggestions(invalid_fields),
    )


def _validate_strict(
    model_class: type[BaseModel],
    data: dict[str, Any],
) -> tuple[list[InvalidField], BaseModel | None]:
    """严格校验：检测 extra fields + 标准 Pydantic 校验

    Returns:
        (invalid_fields, validated_instance_or_None)
    """
    all_invalid: list[InvalidField] = []

    # 1. 检测 extra fields（顶层）
    allowed_keys: set[str] = set()
    for name, field_info in model_class.model_fields.items():
        allowed_keys.add(name)
        if field_info.alias:
            allowed_keys.add(field_info.alias)

    if isinstance(data, dict):
        extra_keys = set(data.keys()) - allowed_keys
        for key in sorted(extra_keys):
            all_invalid.append(InvalidField(
                path=key,
                reason=f"Extra field not permitted: '{key}'",
                error_type=GuardErrorType.EXTRA_FIELD,
                input_value=_truncate(data.get(key)),
            ))

    # 2. 标准 Pydantic 校验
    instance = None
    try:
        instance = model_class.model_validate(data)
    except ValidationError as exc:
        all_invalid.extend(_parse_validation_error(exc))

    return all_invalid, instance


__all__ = [
    "SCHEMA_VERSION",
    "GuardErrorType",
    "GuardResult",
    "InvalidField",
    "guard_crud_config",
]
