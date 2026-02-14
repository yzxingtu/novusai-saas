"""
批量生成结果摘要 + i18n 冲突检测 — 单元测试

覆盖：
- Per-entity 分组摘要
- i18n 冲突检测（同键不同值/嵌套/无冲突）
- deep_merge_with_conflict_detection（保留旧值策略）
- shared_enums v1 边界 warning
- WritePlan → BatchResultSummary 转换
"""

import pytest

from app.codegen.batch_result import (
    BatchResultSummary,
    EntityActionStats,
    I18nConflict,
    build_result_summary,
    check_shared_enums_boundary,
    deep_merge_with_conflict_detection,
    detect_i18n_conflicts,
)
from app.codegen.batch_writer import (
    WritePlan,
    WritePlanAction,
    WritePlanItem,
    WritePlanReason,
    WritePlanSummary,
)


# ============================================================
# i18n 冲突检测
# ============================================================


class TestI18nConflictDetection:
    """i18n 键冲突检测"""

    def test_no_conflict_new_keys(self):
        """新增键不算冲突"""
        existing = {"order": {"title": "订单"}}
        new_data = {"product": {"title": "产品"}}
        conflicts = detect_i18n_conflicts(existing, new_data, "zh.json")
        assert len(conflicts) == 0

    def test_same_value_no_conflict(self):
        """相同值不算冲突"""
        existing = {"order": {"title": "订单"}}
        new_data = {"order": {"title": "订单"}}
        conflicts = detect_i18n_conflicts(existing, new_data, "zh.json")
        assert len(conflicts) == 0

    def test_different_value_conflict(self):
        """不同值产生冲突"""
        existing = {"order": {"title": "订单管理"}}
        new_data = {"order": {"title": "订单列表"}}
        conflicts = detect_i18n_conflicts(
            existing, new_data, "zh.json", source_entity="order",
        )
        assert len(conflicts) == 1
        c = conflicts[0]
        assert c.key == "order.title"
        assert c.existing_value == "订单管理"
        assert c.new_value == "订单列表"
        assert c.source_entity == "order"
        assert c.resolution == "keep_existing"

    def test_nested_conflict(self):
        """嵌套对象中的冲突"""
        existing = {"admin": {"system": {"title": "系统"}}}
        new_data = {"admin": {"system": {"title": "系统设置"}}}
        conflicts = detect_i18n_conflicts(existing, new_data, "zh.json")
        assert len(conflicts) == 1
        assert conflicts[0].key == "admin.system.title"

    def test_multiple_conflicts(self):
        """多个冲突"""
        existing = {"a": "1", "b": "2", "c": "3"}
        new_data = {"a": "x", "b": "y", "c": "3"}
        conflicts = detect_i18n_conflicts(existing, new_data, "test.json")
        assert len(conflicts) == 2  # a 和 b 冲突，c 相同

    def test_two_entities_same_i18n(self):
        """两个实体生成同一个 i18n JSON"""
        base = {}
        entity1_data = {"order": {"title": "订单", "name": "名称"}}
        entity2_data = {"order": {"title": "订单列表"}, "product": {"title": "产品"}}

        # 第一个实体合并（无冲突）
        merged1, c1 = deep_merge_with_conflict_detection(
            base, entity1_data, "zh.json", "order",
        )
        assert len(c1) == 0
        assert merged1["order"]["title"] == "订单"

        # 第二个实体合并（order.title 冲突）
        merged2, c2 = deep_merge_with_conflict_detection(
            merged1, entity2_data, "zh.json", "product",
        )
        assert len(c2) == 1
        assert c2[0].key == "order.title"
        assert c2[0].source_entity == "product"
        # 保留旧值
        assert merged2["order"]["title"] == "订单"
        # 新增键正常添加
        assert merged2["product"]["title"] == "产品"
        # 非冲突键保留
        assert merged2["order"]["name"] == "名称"


# ============================================================
# deep_merge_with_conflict_detection
# ============================================================


class TestDeepMergeKeepExisting:
    """深合并 — 保留旧值策略"""

    def test_new_keys_added(self):
        """新增键被添加"""
        existing = {"a": 1}
        new_data = {"b": 2}
        merged, conflicts = deep_merge_with_conflict_detection(existing, new_data)
        assert merged == {"a": 1, "b": 2}
        assert len(conflicts) == 0

    def test_existing_keys_preserved(self):
        """已有键保留旧值"""
        existing = {"a": "old"}
        new_data = {"a": "new"}
        merged, conflicts = deep_merge_with_conflict_detection(existing, new_data)
        assert merged["a"] == "old"
        assert len(conflicts) == 1

    def test_nested_merge(self):
        """嵌套对象合并"""
        existing = {"a": {"x": 1}}
        new_data = {"a": {"y": 2}}
        merged, conflicts = deep_merge_with_conflict_detection(existing, new_data)
        assert merged == {"a": {"x": 1, "y": 2}}
        assert len(conflicts) == 0

    def test_nested_conflict_keeps_existing(self):
        """嵌套冲突保留旧值"""
        existing = {"a": {"x": "old"}}
        new_data = {"a": {"x": "new"}}
        merged, conflicts = deep_merge_with_conflict_detection(existing, new_data)
        assert merged["a"]["x"] == "old"
        assert len(conflicts) == 1


# ============================================================
# Per-entity 分组摘要
# ============================================================


class TestBuildResultSummary:
    """WritePlan → BatchResultSummary"""

    def _make_plan(self, items: list[WritePlanItem]) -> WritePlan:
        plan = WritePlan(items=items)
        plan.summary = WritePlanSummary(total_files=len(items))
        return plan

    def test_group_by_entity(self):
        """按实体分组"""
        items = [
            WritePlanItem(
                path="backend/app/models/order.py",
                action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE,
                owner="order",
            ),
            WritePlanItem(
                path="backend/app/schemas/order.py",
                action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE,
                owner="order",
            ),
            WritePlanItem(
                path="backend/app/models/product.py",
                action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE,
                owner="product",
            ),
        ]
        plan = self._make_plan(items)
        summary = build_result_summary(plan)

        assert summary.total_entities == 2
        assert len(summary.entities) == 2
        # 按字母序：order, product
        assert summary.entities[0].module == "order"
        assert summary.entities[0].create == 2
        assert summary.entities[0].total == 2
        assert summary.entities[1].module == "product"
        assert summary.entities[1].create == 1

    def test_shared_files(self):
        """共享文件分组"""
        items = [
            WritePlanItem(
                path="backend/app/models/order.py",
                action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE,
                owner="order",
            ),
            WritePlanItem(
                path="backend/app/api/admin/__init__.py",
                action=WritePlanAction.MERGE,
                reason=WritePlanReason.I18N_MERGE,
                owner="",  # shared
            ),
        ]
        plan = self._make_plan(items)
        summary = build_result_summary(plan)

        assert summary.shared.merge == 1
        assert summary.shared.total == 1
        assert len(summary.shared.files) == 1

    def test_entity_file_map_override(self):
        """entity_file_map 覆盖 owner"""
        items = [
            WritePlanItem(
                path="backend/app/models/order.py",
                action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE,
                owner="",  # no owner set
            ),
        ]
        plan = self._make_plan(items)
        entity_map = {"backend/app/models/order.py": "order"}
        summary = build_result_summary(plan, entity_file_map=entity_map)

        assert summary.total_entities == 1
        assert summary.entities[0].module == "order"

    def test_errors_assigned_to_entity(self):
        """错误分配到对应实体"""
        items = [
            WritePlanItem(
                path="backend/app/models/order.py",
                action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE,
                owner="order",
            ),
        ]
        plan = self._make_plan(items)
        errors = [
            {"path": "backend/app/models/order.py", "error": "Permission denied"},
        ]
        entity_map = {"backend/app/models/order.py": "order"}
        summary = build_result_summary(plan, entity_map, errors)

        assert len(summary.entities[0].errors) == 1

    def test_no_entity_map_warning(self):
        """缺少 entity_file_map 时给出 warning"""
        items = [
            WritePlanItem(
                path="test.py",
                action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE,
            ),
        ]
        plan = self._make_plan(items)
        summary = build_result_summary(plan, entity_file_map=None)
        assert any("entity_file_map" in w for w in summary.warnings)

    def test_mixed_actions(self):
        """混合操作统计"""
        items = [
            WritePlanItem(
                path="a.py", action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE, owner="order",
            ),
            WritePlanItem(
                path="b.py", action=WritePlanAction.UPDATE,
                reason=WritePlanReason.CONFLICT_OVERWRITE, owner="order",
            ),
            WritePlanItem(
                path="c.json", action=WritePlanAction.MERGE,
                reason=WritePlanReason.I18N_MERGE, owner="order",
            ),
            WritePlanItem(
                path="d.py", action=WritePlanAction.SKIP,
                reason=WritePlanReason.CONFLICT_SKIP, owner="order",
            ),
        ]
        plan = self._make_plan(items)
        summary = build_result_summary(plan)

        e = summary.entities[0]
        assert e.create == 1
        assert e.update == 1
        assert e.merge == 1
        assert e.skip == 1
        assert e.total == 4

    def test_to_dict(self):
        """to_dict 序列化"""
        items = [
            WritePlanItem(
                path="a.py", action=WritePlanAction.CREATE,
                reason=WritePlanReason.NEW_FILE, owner="order",
            ),
        ]
        plan = self._make_plan(items)
        summary = build_result_summary(plan)
        d = summary.to_dict()

        assert "entities" in d
        assert "shared" in d
        assert "total_files" in d
        assert "i18n_conflicts" in d


# ============================================================
# shared_enums v1 边界
# ============================================================


class TestSharedEnumsBoundary:
    """shared_enums v1 边界声明"""

    def test_no_shared_enums_no_warning(self):
        """没有 shared_enums 不产生 warning"""
        warnings = check_shared_enums_boundary(None)
        assert len(warnings) == 0

    def test_empty_shared_enums_no_warning(self):
        """空 shared_enums 不产生 warning"""
        warnings = check_shared_enums_boundary([])
        assert len(warnings) == 0

    def test_has_shared_enums_warning(self):
        """有 shared_enums 产生 v1 warning"""
        enums = [{"name": "StatusEnum", "values": ["active", "inactive"]}]
        warnings = check_shared_enums_boundary(enums)
        assert len(warnings) == 2
        assert "v1" in warnings[0]
        assert "1 shared_enums" in warnings[1]

    def test_multiple_shared_enums(self):
        """多个 shared_enums"""
        enums = [
            {"name": "StatusEnum", "values": ["active"]},
            {"name": "PriorityEnum", "values": ["high"]},
        ]
        warnings = check_shared_enums_boundary(enums)
        assert "2 shared_enums" in warnings[1]
