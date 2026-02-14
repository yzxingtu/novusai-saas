"""
Batch 工具校验与结构化错误码 — 单元测试

覆盖 4 类错误：
- 校验失败 (Validation)
- 循环依赖 (Dependency)
- 缺失实体 (Missing Entity)
- 写盘异常 (Write Error)
"""

import pytest

from app.codegen.batch_errors import (
    BatchError,
    BatchErrorCategory,
    BatchErrorCode,
    BatchErrorSeverity,
    BatchValidationResult,
    dependency_cycle_detected,
    dependency_order_conflict,
    dependency_order_duplicate,
    dependency_order_missing,
    dependency_unknown_in_order,
    generation_invalid_config,
    generation_render_failed,
    generation_template_error,
    validate_batch_project,
    validation_duplicate_module,
    validation_duplicate_table,
    validation_empty_entities,
    validation_fk_conflict,
    validation_invalid_module_name,
    validation_invalid_table_name,
    validation_m2m_unsupported,
    validation_missing_entity_ref,
    validation_self_reference,
    write_disk_error,
    write_encoding_error,
    write_merge_failed,
    write_permission_denied,
    write_rollback_failed,
    write_unsafe_path,
)
from app.codegen.schemas import (
    BatchCrudProject,
    CrudConfig,
    EntityRelation,
    FieldConfig,
    FieldType,
    RelationType,
    ScopeType,
)


# ============================================================
# Fixtures
# ============================================================


def _make_field(name: str) -> FieldConfig:
    return FieldConfig(
        name=name,
        type=FieldType.STRING,
        label_zh=f"{name}中文",
        label_en=f"{name}_en",
    )


def _make_entity(module: str, table_name: str | None = None) -> CrudConfig:
    return CrudConfig(
        module=module,
        table_name=table_name or f"{module}s",
        display_name=f"{module}管理",
        display_name_en=f"{module.title()} Mgmt",
        scope=ScopeType.TENANT,
        parent_menu="system",
        fields=[_make_field("name")],
    )


def _make_project(
    modules: list[str],
    relations: list[EntityRelation] | None = None,
    generation_order: list[str] | None = None,
) -> BatchCrudProject:
    return BatchCrudProject(
        project_name="Test",
        entities=[_make_entity(m) for m in modules],
        cross_relations=relations or [],
        generation_order=generation_order or [],
    )


# ============================================================
# 1. 校验失败 (Validation)
# ============================================================


class TestValidationErrors:
    """校验类错误的结构一致性"""

    def test_duplicate_module_structure(self):
        err = validation_duplicate_module("order", 2, 0)
        assert err.code == BatchErrorCode.V_DUPLICATE_MODULE
        assert err.category == BatchErrorCategory.VALIDATION
        assert err.severity == BatchErrorSeverity.ERROR
        assert "order" in err.message
        assert err.details["module"] == "order"
        assert err.details["index"] == 2
        assert err.details["first_index"] == 0

    def test_duplicate_table_structure(self):
        err = validation_duplicate_table("orders", 1, 0)
        assert err.code == BatchErrorCode.V_DUPLICATE_TABLE
        assert err.details["table_name"] == "orders"

    def test_missing_entity_ref_structure(self):
        err = validation_missing_entity_ref(
            "source_entity", "nonexistent", 0, ["order", "product"],
        )
        assert err.code == BatchErrorCode.V_MISSING_ENTITY_REF
        assert err.details["value"] == "nonexistent"
        assert err.details["available"] == ["order", "product"]

    def test_self_reference_structure(self):
        err = validation_self_reference("category", 0)
        assert err.code == BatchErrorCode.V_SELF_REFERENCE
        assert err.details["entity"] == "category"

    def test_fk_conflict_structure(self):
        err = validation_fk_conflict("partner_id", "order", 1)
        assert err.code == BatchErrorCode.V_FK_CONFLICT
        assert err.details["foreign_key"] == "partner_id"

    def test_m2m_unsupported_is_warning(self):
        err = validation_m2m_unsupported("order", "product", 0)
        assert err.code == BatchErrorCode.V_M2M_UNSUPPORTED
        assert err.severity == BatchErrorSeverity.WARNING

    def test_empty_entities_structure(self):
        err = validation_empty_entities()
        assert err.code == BatchErrorCode.V_EMPTY_ENTITIES
        assert err.hint

    def test_invalid_module_name(self):
        err = validation_invalid_module_name("Order_Item", "not kebab-case")
        assert err.code == BatchErrorCode.V_INVALID_MODULE_NAME
        assert err.details["module"] == "Order_Item"

    def test_invalid_table_name(self):
        err = validation_invalid_table_name("Order-Items", "not snake_case")
        assert err.code == BatchErrorCode.V_INVALID_TABLE_NAME
        assert err.details["table_name"] == "Order-Items"

    def test_validate_batch_project_duplicate_module(self):
        """validate_batch_project 检测 duplicate module"""
        project = BatchCrudProject(
            project_name="Test",
            entities=[_make_entity("order"), _make_entity("order")],
        )
        result = validate_batch_project(project)
        assert not result.valid
        dup_errors = [
            e for e in result.errors
            if e.code == BatchErrorCode.V_DUPLICATE_MODULE
        ]
        assert len(dup_errors) >= 1

    def test_validate_batch_project_duplicate_table(self):
        """validate_batch_project 检测 duplicate table_name"""
        project = BatchCrudProject(
            project_name="Test",
            entities=[
                _make_entity("order", table_name="shared"),
                _make_entity("product", table_name="shared"),
            ],
        )
        result = validate_batch_project(project)
        assert not result.valid
        dup_errors = [
            e for e in result.errors
            if e.code == BatchErrorCode.V_DUPLICATE_TABLE
        ]
        assert len(dup_errors) >= 1

    def test_validate_batch_project_missing_ref(self):
        """validate_batch_project 检测 missing entity ref"""
        project = _make_project(
            ["order"],
            relations=[EntityRelation(
                source_entity="order",
                target_entity="customer",
                relation_type=RelationType.BELONGS_TO,
            )],
        )
        result = validate_batch_project(project)
        assert not result.valid
        ref_errors = [
            e for e in result.errors
            if e.code == BatchErrorCode.V_MISSING_ENTITY_REF
        ]
        assert len(ref_errors) >= 1

    def test_validate_batch_project_invalid_module(self):
        """validate_batch_project 检测 invalid module name"""
        entity = _make_entity("order")
        entity.module = "Order_Item"  # invalid
        project = BatchCrudProject(
            project_name="Test",
            entities=[entity],
        )
        result = validate_batch_project(project)
        assert not result.valid
        name_errors = [
            e for e in result.errors
            if e.code == BatchErrorCode.V_INVALID_MODULE_NAME
        ]
        assert len(name_errors) == 1


# ============================================================
# 2. 循环依赖 (Dependency)
# ============================================================


class TestDependencyErrors:
    """依赖类错误的结构一致性"""

    def test_cycle_detected_structure(self):
        err = dependency_cycle_detected(["a", "b", "c"])
        assert err.code == BatchErrorCode.D_CYCLE_DETECTED
        assert err.category == BatchErrorCategory.DEPENDENCY
        assert err.details["cycle"] == ["a", "b", "c"]
        assert "a → b → c → a" in err.message

    def test_order_missing_structure(self):
        err = dependency_order_missing(["c"])
        assert err.code == BatchErrorCode.D_ORDER_MISSING_ENTITY
        assert err.details["missing"] == ["c"]

    def test_order_duplicate_structure(self):
        err = dependency_order_duplicate(["a"])
        assert err.code == BatchErrorCode.D_ORDER_DUPLICATE
        assert err.details["duplicates"] == ["a"]

    def test_order_conflict_structure(self):
        err = dependency_order_conflict("a", "b", 0, 1)
        assert err.code == BatchErrorCode.D_ORDER_CONFLICT
        assert err.details["entity"] == "a"
        assert err.details["dependency"] == "b"

    def test_unknown_in_order_structure(self):
        err = dependency_unknown_in_order(["x", "y"])
        assert err.code == BatchErrorCode.D_UNKNOWN_IN_ORDER
        assert err.details["unknown"] == ["x", "y"]

    def test_validate_batch_project_cycle(self):
        """validate_batch_project 检测循环依赖"""
        project = _make_project(
            ["a", "b"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="b",
                    target_entity="a",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
        )
        result = validate_batch_project(project)
        assert not result.valid
        cycle_errors = [
            e for e in result.errors
            if e.code == BatchErrorCode.D_CYCLE_DETECTED
        ]
        assert len(cycle_errors) >= 1

    def test_validate_batch_project_order_conflict(self):
        """validate_batch_project 检测 order 冲突"""
        project = _make_project(
            ["a", "b"],
            relations=[EntityRelation(
                source_entity="a",
                target_entity="b",
                relation_type=RelationType.BELONGS_TO,
            )],
            generation_order=["a", "b"],
        )
        result = validate_batch_project(project)
        assert not result.valid
        conflict_errors = [
            e for e in result.errors
            if e.code == BatchErrorCode.D_ORDER_CONFLICT
        ]
        assert len(conflict_errors) >= 1


# ============================================================
# 3. 缺失实体错误
# ============================================================


class TestMissingEntityErrors:
    """缺失实体错误"""

    def test_validate_missing_source(self):
        project = _make_project(
            ["order"],
            relations=[EntityRelation(
                source_entity="nonexistent",
                target_entity="order",
                relation_type=RelationType.BELONGS_TO,
            )],
        )
        result = validate_batch_project(project)
        assert not result.valid
        missing = [
            e for e in result.errors
            if e.code == BatchErrorCode.V_MISSING_ENTITY_REF
        ]
        assert len(missing) >= 1
        assert "nonexistent" in str(missing[0].details)

    def test_validate_missing_target(self):
        project = _make_project(
            ["order"],
            relations=[EntityRelation(
                source_entity="order",
                target_entity="missing_entity",
                relation_type=RelationType.BELONGS_TO,
            )],
        )
        result = validate_batch_project(project)
        assert not result.valid
        missing = [
            e for e in result.errors
            if e.code == BatchErrorCode.V_MISSING_ENTITY_REF
        ]
        assert any("missing_entity" in str(e.details) for e in missing)


# ============================================================
# 4. 写盘异常 (Write Error)
# ============================================================


class TestWriteErrors:
    """写盘类错误的结构一致性"""

    def test_unsafe_path_structure(self):
        err = write_unsafe_path("../../etc/passwd")
        assert err.code == BatchErrorCode.W_UNSAFE_PATH
        assert err.category == BatchErrorCategory.WRITE
        assert err.details["path"] == "../../etc/passwd"
        assert err.hint

    def test_permission_denied_structure(self):
        err = write_permission_denied("/root/secret.py", "Permission denied")
        assert err.code == BatchErrorCode.W_PERMISSION_DENIED
        assert err.details["path"] == "/root/secret.py"

    def test_merge_failed_structure(self):
        err = write_merge_failed("locales/zh.json", "Invalid JSON")
        assert err.code == BatchErrorCode.W_MERGE_FAILED
        assert err.details["error"] == "Invalid JSON"

    def test_rollback_failed_structure(self):
        err = write_rollback_failed("models/order.py", "File not found")
        assert err.code == BatchErrorCode.W_ROLLBACK_FAILED
        assert err.severity == BatchErrorSeverity.ERROR

    def test_disk_error_structure(self):
        err = write_disk_error("models/order.py", "No space left")
        assert err.code == BatchErrorCode.W_DISK_FULL

    def test_encoding_error_structure(self):
        err = write_encoding_error("data.py", "codec can't decode")
        assert err.code == BatchErrorCode.W_ENCODING_ERROR


# ============================================================
# Generation 类错误
# ============================================================


class TestGenerationErrors:
    """生成类错误的结构一致性"""

    def test_template_error_structure(self):
        err = generation_template_error("order", "model.py.j2", "undefined variable")
        assert err.code == BatchErrorCode.G_TEMPLATE_ERROR
        assert err.category == BatchErrorCategory.GENERATION
        assert err.details["entity"] == "order"
        assert err.details["template"] == "model.py.j2"

    def test_render_failed_structure(self):
        err = generation_render_failed("order", "missing field")
        assert err.code == BatchErrorCode.G_RENDER_FAILED
        assert err.details["entity"] == "order"

    def test_invalid_config_structure(self):
        err = generation_invalid_config("order", "scope is required")
        assert err.code == BatchErrorCode.G_INVALID_CONFIG


# ============================================================
# BatchValidationResult
# ============================================================


class TestBatchValidationResult:
    """BatchValidationResult 的功能"""

    def test_empty_result_is_valid(self):
        result = BatchValidationResult()
        assert result.valid
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_add_error_makes_invalid(self):
        result = BatchValidationResult()
        result.add_error(validation_empty_entities())
        assert not result.valid
        assert result.error_count == 1

    def test_add_warning_keeps_valid(self):
        result = BatchValidationResult()
        result.add_error(validation_m2m_unsupported("a", "b", 0))
        assert result.valid
        assert result.warning_count == 1

    def test_merge_results(self):
        r1 = BatchValidationResult()
        r1.add_error(validation_empty_entities())

        r2 = BatchValidationResult()
        r2.add_error(validation_m2m_unsupported("a", "b", 0))

        r1.merge(r2)
        assert not r1.valid
        assert r1.error_count == 1
        assert r1.warning_count == 1

    def test_to_dict(self):
        result = BatchValidationResult()
        result.add_error(write_unsafe_path("bad/path"))
        d = result.to_dict()
        assert d["valid"] is False
        assert d["error_count"] == 1
        assert len(d["errors"]) == 1
        assert d["errors"][0]["code"] == "W_UNSAFE_PATH"

    def test_error_entity_property(self):
        err = validation_duplicate_module("order", 1, 0)
        assert err.entity == "order"

    def test_error_path_property(self):
        err = write_unsafe_path("bad/path")
        assert err.path == "bad/path"

    def test_valid_project_passes(self):
        """完全合法的项目通过校验"""
        project = _make_project(
            ["order", "customer"],
            relations=[EntityRelation(
                source_entity="order",
                target_entity="customer",
                relation_type=RelationType.BELONGS_TO,
                foreign_key="customer_id",
            )],
            generation_order=["customer", "order"],
        )
        result = validate_batch_project(project)
        assert result.valid
        assert result.error_count == 0

    def test_m2m_is_error(self):
        """many_to_many v1: 作为 error（含结构化修复指引）"""
        project = _make_project(
            ["order", "product"],
            relations=[EntityRelation(
                source_entity="order",
                target_entity="product",
                relation_type=RelationType.MANY_TO_MANY,
            )],
        )
        result = validate_batch_project(project)
        assert not result.valid
        assert result.error_count >= 1
        assert any(
            e.code == BatchErrorCode.V_M2M_UNSUPPORTED
            for e in result.errors
        )
