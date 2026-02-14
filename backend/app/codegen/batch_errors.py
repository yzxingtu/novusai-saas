"""
Batch 工具校验与结构化错误码

统一的错误码体系，覆盖：
- Validation: 实体唯一性、cross_relations 引用合法
- Dependency: 循环依赖、拓扑排序冲突
- WriteError: unsafe path、权限、merge 失败、回滚失败

所有错误走 i18n（使用 _()），前端展示文案使用 $t()。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 错误分类枚举
# ============================================================


class BatchErrorCategory(str, Enum):
    """错误分类"""

    VALIDATION = "validation"
    DEPENDENCY = "dependency"
    WRITE = "write"
    GENERATION = "generation"


class BatchErrorCode(str, Enum):
    """批量操作结构化错误码

    命名规则: {CATEGORY}_{SPECIFIC}
    """

    # ---- Validation (V_*) ----
    V_DUPLICATE_MODULE = "V_DUPLICATE_MODULE"
    V_DUPLICATE_TABLE = "V_DUPLICATE_TABLE"
    V_MISSING_ENTITY_REF = "V_MISSING_ENTITY_REF"
    V_SELF_REFERENCE = "V_SELF_REFERENCE"
    V_FK_CONFLICT = "V_FK_CONFLICT"
    V_M2M_UNSUPPORTED = "V_M2M_UNSUPPORTED"
    V_EMPTY_ENTITIES = "V_EMPTY_ENTITIES"
    V_INVALID_MODULE_NAME = "V_INVALID_MODULE_NAME"
    V_INVALID_TABLE_NAME = "V_INVALID_TABLE_NAME"
    V_MISSING_REQUIRED_FIELD = "V_MISSING_REQUIRED_FIELD"

    # ---- Dependency (D_*) ----
    D_CYCLE_DETECTED = "D_CYCLE_DETECTED"
    D_ORDER_MISSING_ENTITY = "D_ORDER_MISSING_ENTITY"
    D_ORDER_DUPLICATE = "D_ORDER_DUPLICATE"
    D_ORDER_CONFLICT = "D_ORDER_CONFLICT"
    D_UNKNOWN_IN_ORDER = "D_UNKNOWN_IN_ORDER"

    # ---- Write (W_*) ----
    W_UNSAFE_PATH = "W_UNSAFE_PATH"
    W_PERMISSION_DENIED = "W_PERMISSION_DENIED"
    W_MERGE_FAILED = "W_MERGE_FAILED"
    W_ROLLBACK_FAILED = "W_ROLLBACK_FAILED"
    W_DISK_FULL = "W_DISK_FULL"
    W_FILE_LOCKED = "W_FILE_LOCKED"
    W_ENCODING_ERROR = "W_ENCODING_ERROR"
    W_UNEXPECTED = "W_UNEXPECTED"

    # ---- Generation (G_*) ----
    G_TEMPLATE_ERROR = "G_TEMPLATE_ERROR"
    G_RENDER_FAILED = "G_RENDER_FAILED"
    G_INVALID_CONFIG = "G_INVALID_CONFIG"


class BatchErrorSeverity(str, Enum):
    """错误严重级别"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ============================================================
# 结构化错误
# ============================================================


class BatchError(BaseModel):
    """统一的批量操作错误结构

    兼容前端/AI 消费：
    - code: 机器可读的错误码
    - category: 错误分类
    - message: 人类可读的错误信息
    - details: 可选的详情（涉及的 entity/path/field 等）
    - hint: 修复建议
    - severity: error/warning/info
    """

    code: BatchErrorCode = Field(..., description="错误码")
    category: BatchErrorCategory = Field(..., description="错误分类")
    message: str = Field(..., description="人类可读的错误信息")
    details: dict[str, Any] = Field(default_factory=dict, description="详情")
    hint: str = Field("", description="修复建议")
    severity: BatchErrorSeverity = Field(
        BatchErrorSeverity.ERROR, description="严重级别"
    )

    @property
    def entity(self) -> str | None:
        """涉及的实体 module"""
        return self.details.get("entity") or self.details.get("module")

    @property
    def path(self) -> str | None:
        """涉及的文件路径"""
        return self.details.get("path")


class BatchValidationResult(BaseModel):
    """批量校验汇总结果"""

    valid: bool = Field(True, description="是否全部通过")
    errors: list[BatchError] = Field(default_factory=list)
    warnings: list[BatchError] = Field(default_factory=list)

    def add_error(self, error: BatchError) -> None:
        """添加错误"""
        if error.severity == BatchErrorSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.errors.append(error)
            self.valid = False

    def merge(self, other: "BatchValidationResult") -> None:
        """合并另一个校验结果"""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化的字典"""
        return {
            "valid": self.valid,
            "errors": [e.model_dump() for e in self.errors],
            "warnings": [w.model_dump() for w in self.warnings],
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


# ============================================================
# 工厂函数 — Validation 类
# ============================================================


def validation_duplicate_module(
    module: str, index: int, first_index: int,
) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_DUPLICATE_MODULE,
        category=BatchErrorCategory.VALIDATION,
        message=f"Duplicate entity module '{module}' at index {index} (first at {first_index})",
        details={"module": module, "index": index, "first_index": first_index},
        hint=f"Rename one of the '{module}' entities to a unique module name.",
    )


def validation_duplicate_table(
    table_name: str, index: int, first_index: int,
) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_DUPLICATE_TABLE,
        category=BatchErrorCategory.VALIDATION,
        message=f"Duplicate table_name '{table_name}' at index {index} (first at {first_index})",
        details={"table_name": table_name, "index": index, "first_index": first_index},
        hint=f"Rename one of the '{table_name}' tables to a unique table name.",
    )


def validation_missing_entity_ref(
    field: str, value: str, index: int, available: list[str],
) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_MISSING_ENTITY_REF,
        category=BatchErrorCategory.VALIDATION,
        message=f"cross_relations[{index}].{field} '{value}' not found in entities",
        details={
            "field": field,
            "value": value,
            "index": index,
            "available": available,
        },
        hint=f"Add entity '{value}' to the project or fix the reference.",
    )


def validation_self_reference(entity: str, index: int) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_SELF_REFERENCE,
        category=BatchErrorCategory.VALIDATION,
        message=(
            f"cross_relations[{index}]: source and target are the same entity "
            f"'{entity}'. Use self_ref_tree in entity.relations instead."
        ),
        details={"entity": entity, "index": index},
        hint="Use RelationType.SELF_REF_TREE in the entity's own relations list.",
    )


def validation_fk_conflict(
    foreign_key: str, entity: str, index: int,
) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_FK_CONFLICT,
        category=BatchErrorCategory.VALIDATION,
        message=(
            f"cross_relations[{index}]: foreign_key '{foreign_key}' "
            f"conflicts in entity '{entity}' (already used)"
        ),
        details={"foreign_key": foreign_key, "entity": entity, "index": index},
        hint=f"Use a unique foreign_key name for this relation in '{entity}'.",
    )


def validation_m2m_unsupported(
    source: str, target: str, index: int,
) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_M2M_UNSUPPORTED,
        category=BatchErrorCategory.VALIDATION,
        message=(
            f"cross_relations[{index}]: many_to_many between "
            f"'{source}' and '{target}' is not directly supported. "
            f"Create an explicit join entity."
        ),
        details={
            "source": source,
            "target": target,
            "index": index,
            "suggestion": "create_join_entity",
        },
        hint=(
            f"Create a join entity (e.g., '{source}_{target}') "
            f"with two belongs_to relations."
        ),
        severity=BatchErrorSeverity.WARNING,
    )


def validation_empty_entities() -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_EMPTY_ENTITIES,
        category=BatchErrorCategory.VALIDATION,
        message="BatchCrudProject must contain at least one entity.",
        details={},
        hint="Add at least one entity to the project.",
    )


def validation_invalid_module_name(module: str, reason: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_INVALID_MODULE_NAME,
        category=BatchErrorCategory.VALIDATION,
        message=f"Invalid module name '{module}': {reason}",
        details={"module": module, "reason": reason},
        hint="Module names should be kebab-case (e.g., 'order-item').",
    )


def validation_invalid_table_name(table_name: str, reason: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.V_INVALID_TABLE_NAME,
        category=BatchErrorCategory.VALIDATION,
        message=f"Invalid table_name '{table_name}': {reason}",
        details={"table_name": table_name, "reason": reason},
        hint="Table names should be snake_case (e.g., 'order_items').",
    )


# ============================================================
# 工厂函数 — Dependency 类
# ============================================================


def dependency_cycle_detected(cycle: list[str]) -> BatchError:
    return BatchError(
        code=BatchErrorCode.D_CYCLE_DETECTED,
        category=BatchErrorCategory.DEPENDENCY,
        message=f"Circular dependency detected: {' → '.join(cycle + [cycle[0]])}",
        details={"cycle": cycle},
        hint=(
            "Break the cycle by introducing a join entity or "
            "removing one of the circular relations."
        ),
    )


def dependency_order_missing(missing: list[str]) -> BatchError:
    return BatchError(
        code=BatchErrorCode.D_ORDER_MISSING_ENTITY,
        category=BatchErrorCategory.DEPENDENCY,
        message=f"generation_order missing entities: {missing}",
        details={"missing": missing},
        hint="Add all entities to generation_order or leave it empty for auto-sort.",
    )


def dependency_order_duplicate(duplicates: list[str]) -> BatchError:
    return BatchError(
        code=BatchErrorCode.D_ORDER_DUPLICATE,
        category=BatchErrorCategory.DEPENDENCY,
        message=f"generation_order contains duplicates: {duplicates}",
        details={"duplicates": duplicates},
        hint="Remove duplicate entries from generation_order.",
    )


def dependency_order_conflict(
    entity: str, dependency: str, entity_idx: int, dep_idx: int,
) -> BatchError:
    return BatchError(
        code=BatchErrorCode.D_ORDER_CONFLICT,
        category=BatchErrorCategory.DEPENDENCY,
        message=(
            f"generation_order conflict: '{entity}' (index {entity_idx}) "
            f"depends on '{dependency}' (index {dep_idx}), "
            f"but '{entity}' is ordered before '{dependency}'"
        ),
        details={
            "entity": entity,
            "dependency": dependency,
            "entity_index": entity_idx,
            "dependency_index": dep_idx,
        },
        hint=(
            f"Move '{dependency}' before '{entity}' in generation_order, "
            f"or leave it empty for auto-sort."
        ),
    )


def dependency_unknown_in_order(unknown: list[str]) -> BatchError:
    return BatchError(
        code=BatchErrorCode.D_UNKNOWN_IN_ORDER,
        category=BatchErrorCategory.DEPENDENCY,
        message=f"generation_order references unknown entities: {unknown}",
        details={"unknown": unknown},
        hint="Remove unknown entity names from generation_order.",
    )


# ============================================================
# 工厂函数 — Write 类
# ============================================================


def write_unsafe_path(path: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.W_UNSAFE_PATH,
        category=BatchErrorCategory.WRITE,
        message=f"Path '{path}' is not in the allowed whitelist",
        details={"path": path},
        hint="Only paths under backend/app/, backend/tests/, frontend/apps/web-antd/src/ are allowed.",
    )


def write_permission_denied(path: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.W_PERMISSION_DENIED,
        category=BatchErrorCategory.WRITE,
        message=f"Permission denied writing to '{path}': {error}",
        details={"path": path, "error": error},
        hint="Check file permissions and ensure the path is writable.",
    )


def write_merge_failed(path: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.W_MERGE_FAILED,
        category=BatchErrorCategory.WRITE,
        message=f"Failed to merge '{path}': {error}",
        details={"path": path, "error": error},
        hint="The existing file may have invalid JSON or incompatible structure.",
    )


def write_rollback_failed(path: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.W_ROLLBACK_FAILED,
        category=BatchErrorCategory.WRITE,
        message=f"Failed to rollback '{path}': {error}",
        details={"path": path, "error": error},
        hint="Manual file restoration may be needed.",
        severity=BatchErrorSeverity.ERROR,
    )


def write_disk_error(path: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.W_DISK_FULL,
        category=BatchErrorCategory.WRITE,
        message=f"Disk error writing '{path}': {error}",
        details={"path": path, "error": error},
        hint="Check available disk space.",
    )


def write_encoding_error(path: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.W_ENCODING_ERROR,
        category=BatchErrorCategory.WRITE,
        message=f"Encoding error in '{path}': {error}",
        details={"path": path, "error": error},
        hint="Ensure all content is valid UTF-8.",
    )


def write_unexpected_error(path: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.W_UNEXPECTED,
        category=BatchErrorCategory.WRITE,
        message=f"Unexpected error during write at '{path}': {error}",
        details={"path": path, "error": error},
        hint="An unexpected error occurred. Check logs for details.",
    )


# ============================================================
# 工厂函数 — Generation 类
# ============================================================


def generation_template_error(entity: str, template: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.G_TEMPLATE_ERROR,
        category=BatchErrorCategory.GENERATION,
        message=f"Template error for entity '{entity}' ({template}): {error}",
        details={"entity": entity, "template": template, "error": error},
        hint="Check the Jinja2 template for syntax errors.",
    )


def generation_render_failed(entity: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.G_RENDER_FAILED,
        category=BatchErrorCategory.GENERATION,
        message=f"Render failed for entity '{entity}': {error}",
        details={"entity": entity, "error": error},
        hint="Check the entity configuration for invalid values.",
    )


def generation_invalid_config(entity: str, error: str) -> BatchError:
    return BatchError(
        code=BatchErrorCode.G_INVALID_CONFIG,
        category=BatchErrorCategory.GENERATION,
        message=f"Invalid config for entity '{entity}': {error}",
        details={"entity": entity, "error": error},
        hint="Verify all required fields are present and have valid values.",
    )


# ============================================================
# 综合校验入口
# ============================================================


def validate_batch_project(project: "BatchCrudProject") -> BatchValidationResult:
    """对 BatchCrudProject 执行完整校验

    整合 validation + dependency 校验，返回统一的 BatchValidationResult。
    """
    from app.codegen.batch_deps import validate_and_sort, DependencyErrorCode

    result = BatchValidationResult()

    # 1. 基础校验：名称格式
    import re
    _MODULE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
    _TABLE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

    for i, entity in enumerate(project.entities):
        if not _MODULE_RE.match(entity.module):
            result.add_error(validation_invalid_module_name(
                entity.module,
                "Must be kebab-case starting with lowercase letter",
            ))
        if not _TABLE_RE.match(entity.table_name):
            result.add_error(validation_invalid_table_name(
                entity.table_name,
                "Must be snake_case starting with lowercase letter",
            ))

    # 2. 调用 batch_deps 进行依赖校验
    dep_result = validate_and_sort(project)

    # 3. 映射 DependencyError → BatchError
    _DEP_CODE_MAP = {
        DependencyErrorCode.MISSING_ENTITY: BatchErrorCode.V_MISSING_ENTITY_REF,
        DependencyErrorCode.DUPLICATE_MODULE: BatchErrorCode.V_DUPLICATE_MODULE,
        DependencyErrorCode.DUPLICATE_TABLE: BatchErrorCode.V_DUPLICATE_TABLE,
        DependencyErrorCode.CYCLE_DETECTED: BatchErrorCode.D_CYCLE_DETECTED,
        DependencyErrorCode.ORDER_MISSING_ENTITY: BatchErrorCode.D_ORDER_MISSING_ENTITY,
        DependencyErrorCode.ORDER_DUPLICATE: BatchErrorCode.D_ORDER_DUPLICATE,
        DependencyErrorCode.ORDER_DEPENDENCY_CONFLICT: BatchErrorCode.D_ORDER_CONFLICT,
        DependencyErrorCode.SELF_REFERENCE: BatchErrorCode.V_SELF_REFERENCE,
        DependencyErrorCode.FOREIGN_KEY_CONFLICT: BatchErrorCode.V_FK_CONFLICT,
        DependencyErrorCode.MANY_TO_MANY_UNSUPPORTED: BatchErrorCode.V_M2M_UNSUPPORTED,
    }

    _DEP_CATEGORY_MAP = {
        DependencyErrorCode.MISSING_ENTITY: BatchErrorCategory.VALIDATION,
        DependencyErrorCode.DUPLICATE_MODULE: BatchErrorCategory.VALIDATION,
        DependencyErrorCode.DUPLICATE_TABLE: BatchErrorCategory.VALIDATION,
        DependencyErrorCode.CYCLE_DETECTED: BatchErrorCategory.DEPENDENCY,
        DependencyErrorCode.ORDER_MISSING_ENTITY: BatchErrorCategory.DEPENDENCY,
        DependencyErrorCode.ORDER_DUPLICATE: BatchErrorCategory.DEPENDENCY,
        DependencyErrorCode.ORDER_DEPENDENCY_CONFLICT: BatchErrorCategory.DEPENDENCY,
        DependencyErrorCode.SELF_REFERENCE: BatchErrorCategory.VALIDATION,
        DependencyErrorCode.FOREIGN_KEY_CONFLICT: BatchErrorCategory.VALIDATION,
        DependencyErrorCode.MANY_TO_MANY_UNSUPPORTED: BatchErrorCategory.VALIDATION,
    }

    for dep_err in dep_result.errors:
        batch_code = _DEP_CODE_MAP.get(dep_err.code)
        if batch_code:
            result.add_error(BatchError(
                code=batch_code,
                category=_DEP_CATEGORY_MAP.get(dep_err.code, BatchErrorCategory.VALIDATION),
                message=dep_err.message,
                details=dep_err.details,
                severity=BatchErrorSeverity.ERROR,
            ))

    for dep_warn in dep_result.warnings:
        batch_code = _DEP_CODE_MAP.get(dep_warn.code)
        if batch_code:
            result.add_error(BatchError(
                code=batch_code,
                category=_DEP_CATEGORY_MAP.get(dep_warn.code, BatchErrorCategory.VALIDATION),
                message=dep_warn.message,
                details=dep_warn.details,
                severity=BatchErrorSeverity.WARNING,
            ))

    return result


__all__ = [
    "BatchErrorCategory",
    "BatchErrorCode",
    "BatchErrorSeverity",
    "BatchError",
    "BatchValidationResult",
    "validate_batch_project",
    # Validation factories
    "validation_duplicate_module",
    "validation_duplicate_table",
    "validation_missing_entity_ref",
    "validation_self_reference",
    "validation_fk_conflict",
    "validation_m2m_unsupported",
    "validation_empty_entities",
    "validation_invalid_module_name",
    "validation_invalid_table_name",
    # Dependency factories
    "dependency_cycle_detected",
    "dependency_order_missing",
    "dependency_order_duplicate",
    "dependency_order_conflict",
    "dependency_unknown_in_order",
    # Write factories
    "write_unsafe_path",
    "write_permission_denied",
    "write_merge_failed",
    "write_rollback_failed",
    "write_disk_error",
    "write_encoding_error",
    # Generation factories
    "generation_template_error",
    "generation_render_failed",
    "generation_invalid_config",
]
