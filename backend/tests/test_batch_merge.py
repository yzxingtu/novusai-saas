"""
BatchCrudProject 增量合并引擎 — 单元测试

覆盖：
- 新增实体
- 更新实体
- 幂等重放（同一 patch 重放不产生重复）
- touchedPaths 保护
- 边界字段（nullable/default/index）保持稳定
- cross_relations 合并
- shared_enums 合并
- 项目级字段合并
"""

import pytest

from app.codegen.batch_merge import (
    BatchMergePatch,
    BatchMergeResult,
    MergeAction,
    SkipReason,
    merge_batch_project,
)
from app.codegen.schemas import (
    BatchCrudProject,
    CrudConfig,
    EntityRelation,
    EnumDefinition,
    EnumOption,
    FieldConfig,
    FieldType,
    IndexConfig,
    RelationConfig,
    RelationType,
    ScopeType,
)


# ============================================================
# Fixtures
# ============================================================


def _make_field(name: str, **kwargs) -> FieldConfig:
    """快捷创建字段"""
    defaults = {
        "name": name,
        "type": FieldType.STRING,
        "label_zh": f"{name}中文",
        "label_en": f"{name}_en",
    }
    defaults.update(kwargs)
    return FieldConfig(**defaults)


def _make_entity(module: str, fields: list[str] | None = None, **kwargs) -> CrudConfig:
    """快捷创建实体"""
    if fields is None:
        fields = ["name", "description"]
    defaults = {
        "module": module,
        "table_name": f"{module}s",
        "display_name": f"{module}管理",
        "display_name_en": f"{module.title()} Management",
        "scope": ScopeType.TENANT,
        "parent_menu": "system",
        "fields": [_make_field(f) for f in fields],
    }
    defaults.update(kwargs)
    return CrudConfig(**defaults)


def _make_project(entities: list[CrudConfig], **kwargs) -> BatchCrudProject:
    """快捷创建项目"""
    defaults = {
        "project_name": "Test Project",
        "entities": entities,
    }
    defaults.update(kwargs)
    return BatchCrudProject(**defaults)


# ============================================================
# 新增实体
# ============================================================


class TestAddEntity:
    """新增实体合并测试"""

    def test_add_single_entity(self):
        """新增单个实体到空项目"""
        base = _make_project([_make_entity("order")])
        patch = BatchMergePatch(
            entities=[_make_entity("product")],
        )

        result = merge_batch_project(base, patch)

        assert len(result.project.entities) == 2
        modules = [e.module for e in result.project.entities]
        assert "order" in modules
        assert "product" in modules

        assert result.summary.total_added == 1
        entity_summary = next(
            e for e in result.summary.entities if e.module == "product"
        )
        assert entity_summary.action == MergeAction.ADDED

    def test_add_multiple_entities(self):
        """一次性新增多个实体"""
        base = _make_project([_make_entity("order")])
        patch = BatchMergePatch(
            entities=[_make_entity("product"), _make_entity("customer")],
        )

        result = merge_batch_project(base, patch)

        assert len(result.project.entities) == 3
        assert result.summary.total_added == 2


# ============================================================
# 更新实体
# ============================================================


class TestUpdateEntity:
    """更新已有实体合并测试"""

    def test_update_fields(self):
        """更新实体的字段"""
        base = _make_project([
            _make_entity("order", fields=["name"]),
        ])
        patch = BatchMergePatch(
            entities=[_make_entity("order", fields=["name", "amount"])],
        )

        result = merge_batch_project(base, patch)

        assert len(result.project.entities) == 1
        order = result.project.entities[0]
        field_names = [f.name for f in order.fields]
        assert "name" in field_names
        assert "amount" in field_names

        entity_summary = result.summary.entities[0]
        assert entity_summary.action == MergeAction.UPDATED
        added_changes = [
            c for c in entity_summary.changes
            if c.action == MergeAction.ADDED and c.path.startswith("fields.")
        ]
        assert len(added_changes) == 1
        assert added_changes[0].path == "fields.amount"

    def test_update_field_properties(self):
        """更新字段的属性"""
        base = _make_project([
            _make_entity("order", fields=[]),
        ])
        base.entities[0].fields = [_make_field("name", max_length=50)]

        patch_entity = _make_entity("order", fields=[])
        patch_entity.fields = [_make_field("name", max_length=100)]
        patch = BatchMergePatch(entities=[patch_entity])

        result = merge_batch_project(base, patch)

        order = result.project.entities[0]
        name_field = next(f for f in order.fields if f.name == "name")
        assert name_field.max_length == 100

    def test_update_scalar_field(self):
        """更新实体的标量字段"""
        base = _make_project([_make_entity("order")])
        patch = BatchMergePatch(
            entities=[_make_entity("order", display_name="订单管理v2")],
        )

        result = merge_batch_project(base, patch)

        assert result.project.entities[0].display_name == "订单管理v2"


# ============================================================
# 幂等重放
# ============================================================


class TestIdempotent:
    """幂等合并测试"""

    def test_same_patch_no_duplicate_fields(self):
        """同一 patch 重放不产生重复字段"""
        base = _make_project([_make_entity("order", fields=["name", "amount"])])
        patch = BatchMergePatch(
            entities=[_make_entity("order", fields=["name", "amount"])],
        )

        result1 = merge_batch_project(base, patch)
        result2 = merge_batch_project(result1.project, patch)

        assert len(result2.project.entities[0].fields) == 2

    def test_same_patch_no_duplicate_relations(self):
        """同一 patch 重放不产生重复关联"""
        base_entity = _make_entity("order")
        base_entity.relations = [RelationConfig(
            name="customer",
            type=RelationType.BELONGS_TO,
            target_model="Customer",
            target_table="customers",
        )]
        base = _make_project([base_entity])

        patch_entity = _make_entity("order")
        patch_entity.relations = [RelationConfig(
            name="customer",
            type=RelationType.BELONGS_TO,
            target_model="Customer",
            target_table="customers",
        )]
        patch = BatchMergePatch(entities=[patch_entity])

        result1 = merge_batch_project(base, patch)
        result2 = merge_batch_project(result1.project, patch)

        assert len(result2.project.entities[0].relations) == 1

    def test_same_patch_no_duplicate_enums(self):
        """同一 patch 重放不产生重复枚举"""
        enum = EnumDefinition(
            name="OrderStatus",
            values=[
                EnumOption(value="draft", label_zh="草稿", label_en="Draft"),
                EnumOption(value="published", label_zh="已发布", label_en="Published"),
            ],
        )
        base_entity = _make_entity("order")
        base_entity.enums = [enum]
        base = _make_project([base_entity])

        patch_entity = _make_entity("order")
        patch_entity.enums = [enum]
        patch = BatchMergePatch(entities=[patch_entity])

        result1 = merge_batch_project(base, patch)
        result2 = merge_batch_project(result1.project, patch)

        assert len(result2.project.entities[0].enums) == 1

    def test_same_patch_no_duplicate_indexes(self):
        """同一 patch 重放不产生重复索引"""
        idx = IndexConfig(fields=["tenant_id", "created_at"])
        base_entity = _make_entity("order")
        base_entity.indexes = [idx]
        base = _make_project([base_entity])

        patch_entity = _make_entity("order")
        patch_entity.indexes = [idx]
        patch = BatchMergePatch(entities=[patch_entity])

        result1 = merge_batch_project(base, patch)
        result2 = merge_batch_project(result1.project, patch)

        assert len(result2.project.entities[0].indexes) == 1

    def test_triple_replay(self):
        """三次重放结果一致"""
        base = _make_project([_make_entity("order")])
        patch = BatchMergePatch(
            entities=[_make_entity("order", fields=["name", "price"])],
        )

        r1 = merge_batch_project(base, patch)
        r2 = merge_batch_project(r1.project, patch)
        r3 = merge_batch_project(r2.project, patch)

        assert r2.project.model_dump() == r3.project.model_dump()


# ============================================================
# touchedPaths 保护
# ============================================================


class TestTouchedPaths:
    """touchedPaths 保护测试"""

    def test_fields_protected(self):
        """fields 被 touchedPaths 保护时不被覆盖"""
        base = _make_project([_make_entity("order", fields=["name"])])
        patch = BatchMergePatch(
            entities=[_make_entity("order", fields=["name", "amount"])],
        )

        result = merge_batch_project(
            base, patch,
            touched_paths={"order": {"fields"}},
        )

        order = result.project.entities[0]
        assert len(order.fields) == 1
        assert order.fields[0].name == "name"

        entity_summary = result.summary.entities[0]
        skipped = [c for c in entity_summary.changes if c.skip_reason == SkipReason.TOUCHED_PATH]
        assert any(c.path == "fields" for c in skipped)

    def test_relations_protected(self):
        """relations 被 touchedPaths 保护"""
        base_entity = _make_entity("order")
        base_entity.relations = [RelationConfig(
            name="customer",
            type=RelationType.BELONGS_TO,
            target_model="Customer",
            target_table="customers",
        )]
        base = _make_project([base_entity])

        patch_entity = _make_entity("order")
        patch_entity.relations = [
            RelationConfig(
                name="customer",
                type=RelationType.BELONGS_TO,
                target_model="Customer",
                target_table="customers",
            ),
            RelationConfig(
                name="product",
                type=RelationType.BELONGS_TO,
                target_model="Product",
                target_table="products",
            ),
        ]
        patch = BatchMergePatch(entities=[patch_entity])

        result = merge_batch_project(
            base, patch,
            touched_paths={"order": {"relations"}},
        )

        assert len(result.project.entities[0].relations) == 1

    def test_scalar_protected(self):
        """标量字段被 touchedPaths 保护"""
        base = _make_project([_make_entity("order", display_name="原始名称")])
        patch = BatchMergePatch(
            entities=[_make_entity("order", display_name="AI修改的名称")],
        )

        result = merge_batch_project(
            base, patch,
            touched_paths={"order": {"display_name"}},
        )

        assert result.project.entities[0].display_name == "原始名称"

    def test_unprotected_paths_still_merge(self):
        """未保护的路径正常合并"""
        base = _make_project([_make_entity("order", fields=["name"])])
        patch = BatchMergePatch(
            entities=[_make_entity("order", fields=["name", "amount"], display_name="新名称")],
        )

        result = merge_batch_project(
            base, patch,
            touched_paths={"order": {"fields"}},
        )

        # fields 被保护
        assert len(result.project.entities[0].fields) == 1
        # display_name 未保护，正常更新
        assert result.project.entities[0].display_name == "新名称"

    def test_project_level_touched(self):
        """项目级字段被 touchedPaths 保护"""
        base = _make_project([_make_entity("order")], project_name="Original")
        patch = BatchMergePatch(project_name="AI Changed")

        result = merge_batch_project(
            base, patch,
            touched_paths={"__project__": {"project_name"}},
        )

        assert result.project.project_name == "Original"


# ============================================================
# 边界字段稳定性
# ============================================================


class TestEdgeCases:
    """边界字段稳定性测试"""

    def test_nullable_default_index_stable(self):
        """nullable/default/index 等边界字段保持稳定"""
        base_entity = _make_entity("order", fields=[])
        base_entity.fields = [FieldConfig(
            name="amount",
            type=FieldType.DECIMAL,
            label_zh="金额",
            label_en="Amount",
            nullable=False,
            default="0.00",
            index=True,
            required=True,
            unique=False,
        )]
        base = _make_project([base_entity])

        # patch 不修改该字段
        patch = BatchMergePatch(
            entities=[_make_entity("order", fields=["name"])],
        )

        result = merge_batch_project(base, patch)

        order = result.project.entities[0]
        amount = next(f for f in order.fields if f.name == "amount")
        assert amount.nullable is False
        assert amount.default == "0.00"
        assert amount.index is True
        assert amount.required is True

    def test_empty_patch(self):
        """空 patch 不改变任何内容"""
        base = _make_project([_make_entity("order")])
        patch = BatchMergePatch()

        result = merge_batch_project(base, patch)

        assert result.project.model_dump() == base.model_dump()

    def test_delete_not_allowed(self):
        """合并不会删除实体"""
        base = _make_project([_make_entity("order"), _make_entity("product")])
        # patch 只包含 order，不包含 product
        patch = BatchMergePatch(
            entities=[_make_entity("order", display_name="新名称")],
        )

        result = merge_batch_project(base, patch)

        # product 仍然存在
        assert len(result.project.entities) == 2
        modules = [e.module for e in result.project.entities]
        assert "product" in modules


# ============================================================
# cross_relations 合并
# ============================================================


class TestCrossRelationsMerge:
    """cross_relations 合并测试"""

    def test_add_cross_relation(self):
        """新增跨表关联"""
        base = _make_project([_make_entity("order"), _make_entity("customer")])
        patch = BatchMergePatch(
            cross_relations=[EntityRelation(
                source_entity="order",
                target_entity="customer",
                relation_type=RelationType.BELONGS_TO,
                foreign_key="customer_id",
            )],
        )

        result = merge_batch_project(base, patch)

        assert len(result.project.cross_relations) == 1
        assert result.summary.cross_relations is not None
        assert result.summary.cross_relations.action == MergeAction.UPDATED

    def test_cross_relation_idempotent(self):
        """跨表关联重放幂等"""
        rel = EntityRelation(
            source_entity="order",
            target_entity="customer",
            relation_type=RelationType.BELONGS_TO,
            foreign_key="customer_id",
        )
        base = _make_project(
            [_make_entity("order"), _make_entity("customer")],
            cross_relations=[rel],
        )
        patch = BatchMergePatch(cross_relations=[rel])

        result = merge_batch_project(base, patch)

        assert len(result.project.cross_relations) == 1


# ============================================================
# shared_enums 合并
# ============================================================


class TestSharedEnumsMerge:
    """shared_enums 合并测试"""

    def test_add_shared_enum(self):
        """新增共享枚举"""
        base = _make_project([_make_entity("order")])
        patch = BatchMergePatch(
            shared_enums=[EnumDefinition(
                name="Priority",
                values=[
                    EnumOption(value="low", label_zh="低", label_en="Low"),
                    EnumOption(value="high", label_zh="高", label_en="High"),
                ],
            )],
        )

        result = merge_batch_project(base, patch)

        assert len(result.project.shared_enums) == 1
        assert result.project.shared_enums[0].name == "Priority"

    def test_shared_enum_idempotent(self):
        """共享枚举重放幂等"""
        enum = EnumDefinition(
            name="Priority",
            values=[
                EnumOption(value="low", label_zh="低", label_en="Low"),
            ],
        )
        base = _make_project([_make_entity("order")], shared_enums=[enum])
        patch = BatchMergePatch(shared_enums=[enum])

        result = merge_batch_project(base, patch)

        assert len(result.project.shared_enums) == 1


# ============================================================
# generation_order 合并
# ============================================================


class TestGenerationOrderMerge:
    """generation_order 合并测试"""

    def test_update_generation_order(self):
        """更新生成顺序"""
        base = _make_project(
            [_make_entity("order"), _make_entity("customer")],
            generation_order=["customer", "order"],
        )
        patch = BatchMergePatch(generation_order=["order", "customer"])

        result = merge_batch_project(base, patch)

        assert result.project.generation_order == ["order", "customer"]

    def test_generation_order_protected(self):
        """生成顺序被 touchedPaths 保护"""
        base = _make_project(
            [_make_entity("order"), _make_entity("customer")],
            generation_order=["customer", "order"],
        )
        patch = BatchMergePatch(generation_order=["order", "customer"])

        result = merge_batch_project(
            base, patch,
            touched_paths={"__project__": {"generation_order"}},
        )

        assert result.project.generation_order == ["customer", "order"]


# ============================================================
# merge_summary 输出
# ============================================================


class TestMergeSummary:
    """merge_summary 输出测试"""

    def test_summary_counts(self):
        """验证 summary 的统计"""
        base = _make_project([_make_entity("order")])
        patch = BatchMergePatch(
            entities=[
                _make_entity("order", display_name="新名称"),
                _make_entity("product"),
            ],
        )

        result = merge_batch_project(base, patch)

        assert result.summary.total_added == 1
        assert result.summary.total_updated == 1

    def test_summary_skip_reason(self):
        """验证 skip_reason 包含 touchedPaths 命中原因"""
        base = _make_project([_make_entity("order", fields=["name"])])
        patch = BatchMergePatch(
            entities=[_make_entity("order", fields=["name", "amount"])],
        )

        result = merge_batch_project(
            base, patch,
            touched_paths={"order": {"fields"}},
        )

        entity_summary = result.summary.entities[0]
        skipped = [c for c in entity_summary.changes if c.skip_reason is not None]
        assert len(skipped) >= 1
        assert all(c.skip_reason == SkipReason.TOUCHED_PATH for c in skipped)
