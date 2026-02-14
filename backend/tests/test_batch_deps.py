"""
多表依赖排序与 cross_relations 强校验 — 单元测试

覆盖：
- 3-4 实体链式依赖
- 菱形依赖
- 循环依赖
- 缺失实体
- 顺序冲突
- module/table_name 唯一性
- foreign_key 冲突
- many_to_many 策略
"""

import pytest

from app.codegen.batch_deps import (
    DependencyErrorCode,
    ValidationResult,
    resolve_generation_order,
    validate_and_sort,
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
# 链式依赖 (A → B → C)
# ============================================================


class TestChainDependency:
    """3 实体链式依赖"""

    def test_chain_a_b_c(self):
        """A belongs_to B, B belongs_to C → 顺序 C, B, A"""
        project = _make_project(
            ["a", "b", "c"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="b_id",
                ),
                EntityRelation(
                    source_entity="b",
                    target_entity="c",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="c_id",
                ),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is True
        assert result.resolved_order == ["c", "b", "a"]

    def test_four_entity_chain(self):
        """4 实体链式 D → C → B → A"""
        project = _make_project(
            ["a", "b", "c", "d"],
            relations=[
                EntityRelation(
                    source_entity="d",
                    target_entity="c",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="c",
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

        result = validate_and_sort(project)

        assert result.valid is True
        order = result.resolved_order
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")
        assert order.index("c") < order.index("d")


# ============================================================
# 菱形依赖
# ============================================================


class TestDiamondDependency:
    """菱形依赖: A → B, A → C, B → D, C → D"""

    def test_diamond(self):
        project = _make_project(
            ["a", "b", "c", "d"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="a",
                    target_entity="c",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="b",
                    target_entity="d",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="c",
                    target_entity="d",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is True
        order = result.resolved_order
        # d 必须在 b, c 之前
        assert order.index("d") < order.index("b")
        assert order.index("d") < order.index("c")
        # b, c 必须在 a 之前
        assert order.index("b") < order.index("a")
        assert order.index("c") < order.index("a")


# ============================================================
# 循环依赖
# ============================================================


class TestCycleDependency:
    """循环依赖检测"""

    def test_simple_cycle(self):
        """A → B → A"""
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

        result = validate_and_sort(project)

        assert result.valid is False
        cycle_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.CYCLE_DETECTED
        ]
        assert len(cycle_errors) >= 1
        # cycle 路径中应包含 a 和 b
        cycle_details = cycle_errors[0].details
        assert "cycle" in cycle_details

    def test_three_way_cycle(self):
        """A → B → C → A"""
        project = _make_project(
            ["a", "b", "c"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="b",
                    target_entity="c",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="c",
                    target_entity="a",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        cycle_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.CYCLE_DETECTED
        ]
        assert len(cycle_errors) >= 1


# ============================================================
# 缺失实体
# ============================================================


class TestMissingEntity:
    """引用不存在的实体"""

    def test_missing_source(self):
        project = _make_project(
            ["order"],
            relations=[
                EntityRelation(
                    source_entity="nonexistent",
                    target_entity="order",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        missing_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.MISSING_ENTITY
        ]
        assert len(missing_errors) >= 1
        assert "nonexistent" in missing_errors[0].details.get("value", "")

    def test_missing_target(self):
        project = _make_project(
            ["order"],
            relations=[
                EntityRelation(
                    source_entity="order",
                    target_entity="customer",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        missing_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.MISSING_ENTITY
        ]
        assert any("customer" in str(e.details) for e in missing_errors)


# ============================================================
# generation_order 顺序冲突
# ============================================================


class TestOrderConflict:
    """generation_order 与依赖冲突"""

    def test_order_dependency_conflict(self):
        """order 中 A 排在 B 前面，但 A depends_on B"""
        project = _make_project(
            ["a", "b"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
            generation_order=["a", "b"],  # A 先于 B，但 A 依赖 B
        )

        result = validate_and_sort(project)

        assert result.valid is False
        conflict_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.ORDER_DEPENDENCY_CONFLICT
        ]
        assert len(conflict_errors) >= 1

    def test_order_missing_entity(self):
        """generation_order 缺少实体"""
        project = _make_project(
            ["a", "b", "c"],
            generation_order=["a", "b"],  # 缺少 c
        )

        result = validate_and_sort(project)

        assert result.valid is False
        missing_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.ORDER_MISSING_ENTITY
        ]
        assert len(missing_errors) == 1

    def test_order_duplicate(self):
        """generation_order 有重复"""
        project = _make_project(
            ["a", "b"],
            generation_order=["a", "b", "a"],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        dup_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.ORDER_DUPLICATE
        ]
        assert len(dup_errors) == 1

    def test_valid_order(self):
        """合法的 generation_order"""
        project = _make_project(
            ["a", "b"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
            generation_order=["b", "a"],  # B 先于 A，A 依赖 B ✓
        )

        result = validate_and_sort(project)

        assert result.valid is True


# ============================================================
# 实体唯一性
# ============================================================


class TestEntityUniqueness:
    """module/table_name 唯一性"""

    def test_duplicate_module(self):
        project = BatchCrudProject(
            project_name="Test",
            entities=[_make_entity("order"), _make_entity("order")],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        dup_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.DUPLICATE_MODULE
        ]
        assert len(dup_errors) == 1

    def test_duplicate_table_name(self):
        project = BatchCrudProject(
            project_name="Test",
            entities=[
                _make_entity("order", table_name="shared_table"),
                _make_entity("product", table_name="shared_table"),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        dup_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.DUPLICATE_TABLE
        ]
        assert len(dup_errors) == 1


# ============================================================
# foreign_key 冲突
# ============================================================


class TestForeignKeyConflict:
    """外键冲突检测"""

    def test_fk_conflict_same_entity(self):
        """同一实体上两个 belongs_to 使用相同 FK"""
        project = _make_project(
            ["order", "customer", "supplier"],
            relations=[
                EntityRelation(
                    source_entity="order",
                    target_entity="customer",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="partner_id",
                ),
                EntityRelation(
                    source_entity="order",
                    target_entity="supplier",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="partner_id",  # 冲突
                ),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        fk_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.FOREIGN_KEY_CONFLICT
        ]
        assert len(fk_errors) == 1


# ============================================================
# many_to_many 策略
# ============================================================


class TestManyToMany:
    """多对多关系策略"""

    def test_many_to_many_error(self):
        """many_to_many 应给出 error（含结构化修复指引）"""
        project = _make_project(
            ["order", "product"],
            relations=[
                EntityRelation(
                    source_entity="order",
                    target_entity="product",
                    relation_type=RelationType.MANY_TO_MANY,
                ),
            ],
        )

        result = validate_and_sort(project)

        # many_to_many v1: 作为 error
        assert result.valid is False
        m2m_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.MANY_TO_MANY_UNSUPPORTED
        ]
        assert len(m2m_errors) == 1
        assert "join entity" in m2m_errors[0].message.lower()

        # 结构化修复指引
        fix = m2m_errors[0].details.get("fix", {})
        assert fix["join_entity_module"] == "order_product"
        assert len(fix["add_relations"]) == 2
        assert fix["add_relations"][0]["relation_type"] == "belongs_to"
        assert fix["add_relations"][1]["relation_type"] == "belongs_to"

    def test_explicit_join_entity_passes(self):
        """显式 join entity 的 3 表配置可通过校验"""
        project = _make_project(
            ["user", "role", "user_role"],
            relations=[
                EntityRelation(
                    source_entity="user_role",
                    target_entity="user",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="user_id",
                ),
                EntityRelation(
                    source_entity="user_role",
                    target_entity="role",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="role_id",
                ),
            ],
        )

        result = validate_and_sort(project)
        assert result.valid is True

        # user_role 依赖 user 和 role
        order = result.resolved_order
        assert order.index("user") < order.index("user_role")
        assert order.index("role") < order.index("user_role")


# ============================================================
# self_reference
# ============================================================


class TestSelfReference:
    """cross_relations 中的自引用"""

    def test_self_reference_error(self):
        project = _make_project(
            ["category"],
            relations=[
                EntityRelation(
                    source_entity="category",
                    target_entity="category",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
        )

        result = validate_and_sort(project)

        assert result.valid is False
        self_ref_errors = [
            e for e in result.errors
            if e.code == DependencyErrorCode.SELF_REFERENCE
        ]
        assert len(self_ref_errors) == 1


# ============================================================
# resolve_generation_order
# ============================================================


class TestResolveOrder:
    """resolve_generation_order 便捷函数"""

    def test_auto_resolve_when_empty(self):
        """generation_order 为空时自动推导"""
        project = _make_project(
            ["a", "b", "c"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
                EntityRelation(
                    source_entity="b",
                    target_entity="c",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
        )

        order = resolve_generation_order(project)

        assert order == ["c", "b", "a"]

    def test_use_provided_order_when_valid(self):
        """合法 generation_order 直接使用"""
        project = _make_project(
            ["a", "b", "c"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
            generation_order=["c", "b", "a"],
        )

        order = resolve_generation_order(project)

        assert order == ["c", "b", "a"]

    def test_fallback_when_order_invalid(self):
        """无效 generation_order 回退到自动推导"""
        project = _make_project(
            ["a", "b"],
            relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                ),
            ],
            generation_order=["a", "b"],  # 冲突
        )

        order = resolve_generation_order(project)

        assert order == ["b", "a"]

    def test_no_deps_stable_sort(self):
        """无依赖时按字母序稳定排序"""
        project = _make_project(["zebra", "alpha", "middle"])

        order = resolve_generation_order(project)

        assert order == ["alpha", "middle", "zebra"]

    def test_has_many_dependency(self):
        """has_many: target 依赖 source"""
        project = _make_project(
            ["order", "order_item"],
            relations=[
                EntityRelation(
                    source_entity="order",
                    target_entity="order_item",
                    relation_type=RelationType.HAS_MANY,
                    foreign_key="order_id",
                ),
            ],
        )

        order = resolve_generation_order(project)

        # order_item 含 FK → order_item 依赖 order → order 先
        assert order.index("order") < order.index("order_item")
