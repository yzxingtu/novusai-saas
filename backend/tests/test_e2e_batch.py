"""
多表批量生成 E2E 回归用例

M58-T8: 端到端回归，确保多表批量生成在各种场景下稳定运行。

覆盖：
1. 3-4 表项目：belongs_to + has_many + 显式 join entity
2. 全链路：validate → write_plan → execute_write
3. 冲突策略：skip / overwrite / merge
4. 异常：循环依赖、缺失实体、非法 cross_relations
5. 追问协议：缺失信息触发 clarify
6. 自检：生成后 self_check
7. Undo bundle：生成→导出→回滚
"""

import json
import os
import shutil
import tempfile

import pytest

from app.codegen.batch_deps import validate_and_sort
from app.codegen.batch_errors import validate_batch_project
from app.codegen.batch_merge import BatchMergePatch, merge_batch_project
from app.codegen.batch_writer import AtomicBatchWriter, WritePlanAction
from app.codegen.clarify import detect_missing_info
from app.codegen.schemas import (
    BatchCrudProject,
    CrudConfig,
    EntityRelation,
    FieldConfig,
    RelationType,
)
from app.codegen.self_check import run_self_check
from app.codegen.snapshot import export_snapshot, import_snapshot
from app.codegen.undo_bundle import build_undo_bundle, apply_revert
from app.codegen.writer import ConflictAction


# ============================================================
# Fixtures: 3-4 表项目
# ============================================================

def _field(name: str, ftype: str = "string", **kw) -> FieldConfig:
    return FieldConfig(
        name=name,
        type=ftype,
        label=name.replace("_", " ").title(),
        label_zh=name,
        label_en=name.replace("_", " ").title(),
        **kw,
    )


def _entity(module: str, table: str, fields: list[FieldConfig]) -> CrudConfig:
    return CrudConfig(
        module=module,
        table_name=table,
        display_name=module,
        display_name_en=module.title(),
        parent_menu="test",
        fields=fields,
    )


def make_order_system() -> BatchCrudProject:
    """3 表：customer → order → order-item (belongs_to 链)"""
    customer = _entity("customer", "customers", [
        _field("name"),
        _field("email"),
        _field("phone"),
    ])
    order = _entity("order", "orders", [
        _field("order_no"),
        _field("amount", "decimal"),
        _field("customer_id", "integer"),
    ])
    order_item = _entity("order-item", "order_items", [
        _field("product_name"),
        _field("quantity", "integer"),
        _field("price", "decimal"),
        _field("order_id", "integer"),
    ])

    return BatchCrudProject(
        project_name="order-system",
        description="Order management",
        entities=[customer, order, order_item],
        cross_relations=[
            EntityRelation(
                source_entity="order",
                target_entity="customer",
                relation_type=RelationType.BELONGS_TO,
                foreign_key="customer_id",
            ),
            EntityRelation(
                source_entity="order-item",
                target_entity="order",
                relation_type=RelationType.BELONGS_TO,
                foreign_key="order_id",
            ),
        ],
        generation_order=["customer", "order", "order-item"],
    )


def make_user_role_system() -> BatchCrudProject:
    """4 表：user, role, user-role (join entity), permission"""
    user = _entity("user", "users", [
        _field("username"),
        _field("email"),
    ])
    role = _entity("role", "roles", [
        _field("name"),
        _field("description", "text"),
    ])
    user_role = _entity("user-role", "user_roles", [
        _field("user_id", "integer"),
        _field("role_id", "integer"),
    ])
    permission = _entity("permission", "permissions", [
        _field("code"),
        _field("name"),
        _field("role_id", "integer"),
    ])

    return BatchCrudProject(
        project_name="rbac-system",
        description="RBAC with join entity",
        entities=[user, role, user_role, permission],
        cross_relations=[
            EntityRelation(
                source_entity="user-role",
                target_entity="user",
                relation_type=RelationType.BELONGS_TO,
                foreign_key="user_id",
            ),
            EntityRelation(
                source_entity="user-role",
                target_entity="role",
                relation_type=RelationType.BELONGS_TO,
                foreign_key="role_id",
            ),
            EntityRelation(
                source_entity="permission",
                target_entity="role",
                relation_type=RelationType.BELONGS_TO,
                foreign_key="role_id",
            ),
        ],
        generation_order=["user", "role", "user-role", "permission"],
    )


# ============================================================
# 1. 全链路：validate → write_plan → execute
# ============================================================


class TestFullPipeline:
    """全链路回归"""

    def test_order_system_validate(self):
        """3 表 order system validate 通过"""
        project = make_order_system()
        result = validate_and_sort(project)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_user_role_system_validate(self):
        """4 表 join entity system validate 通过"""
        project = make_user_role_system()
        result = validate_and_sort(project)
        assert result.valid is True

    def test_order_system_batch_errors(self):
        """batch_errors 层校验也通过"""
        project = make_order_system()
        result = validate_batch_project(project)
        assert result.valid is True

    def test_write_plan_generation(self):
        """生成 WritePlan 不触盘"""
        tmp_dir = tempfile.mkdtemp(prefix="e2e_wp_")
        try:
            writer = AtomicBatchWriter(tmp_dir)
            files = {
                "backend/app/models/order.py": "class Order: pass\n",
                "backend/app/models/customer.py": "class Customer: pass\n",
            }
            plan = writer.create_write_plan(files)
            assert plan.summary.total_files == 2
            assert plan.summary.create_count == 2
            assert plan.summary.skip_count == 0
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_execute_write_creates_files(self):
        """写盘执行实际创建文件"""
        tmp_dir = tempfile.mkdtemp(prefix="e2e_exec_")
        try:
            writer = AtomicBatchWriter(tmp_dir)
            files = {
                "backend/app/models/order.py": "class Order: pass\n",
                "backend/app/models/customer.py": "class Customer: pass\n",
            }
            plan = writer.create_write_plan(files)
            result = writer.execute_write_plan(files, plan)

            assert len(result.written) == 2
            assert len(result.errors) == 0

            # 验证文件实际存在
            for rel_path in files:
                abs_path = os.path.join(tmp_dir, rel_path)
                assert os.path.exists(abs_path), f"File not created: {rel_path}"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# 2. 冲突策略
# ============================================================


class TestConflictStrategies:
    """冲突策略回归"""

    def _setup_existing(self, tmp_dir: str) -> dict[str, str]:
        """预置已存在的文件"""
        existing = {
            "backend/app/models/order.py": "# user modified\nclass Order: pass\n",
        }
        for rel, content in existing.items():
            abs_path = os.path.join(tmp_dir, rel)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
        return existing

    def test_skip_strategy(self):
        """skip 策略：已存在的文件不覆盖"""
        tmp_dir = tempfile.mkdtemp(prefix="e2e_skip_")
        try:
            self._setup_existing(tmp_dir)
            writer = AtomicBatchWriter(tmp_dir)

            files = {
                "backend/app/models/order.py": "class Order:\n    NEW = True\n",
                "backend/app/models/customer.py": "class Customer: pass\n",
            }
            plan = writer.create_write_plan(
                files, conflict_action=ConflictAction.SKIP,
            )

            # order.py 应该被 skip
            order_item = next(
                i for i in plan.items if "order.py" in i.path
            )
            assert order_item.action == WritePlanAction.SKIP

            result = writer.execute_write_plan(
                files, plan, conflict_action=ConflictAction.SKIP,
            )
            assert "backend/app/models/order.py" in result.skipped

            # 验证原文件未被修改
            with open(
                os.path.join(tmp_dir, "backend/app/models/order.py"),
                encoding="utf-8",
            ) as f:
                assert "user modified" in f.read()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_overwrite_strategy(self):
        """overwrite 策略：覆盖已存在的文件"""
        tmp_dir = tempfile.mkdtemp(prefix="e2e_ow_")
        try:
            self._setup_existing(tmp_dir)
            writer = AtomicBatchWriter(tmp_dir)

            files = {
                "backend/app/models/order.py": "class Order:\n    NEW = True\n",
            }
            plan = writer.create_write_plan(
                files, conflict_action=ConflictAction.OVERWRITE,
            )
            result = writer.execute_write_plan(
                files, plan, conflict_action=ConflictAction.OVERWRITE,
            )
            assert len(result.written) == 1

            with open(
                os.path.join(tmp_dir, "backend/app/models/order.py"),
                encoding="utf-8",
            ) as f:
                content = f.read()
                assert "NEW = True" in content
                assert "user modified" not in content
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_merge_i18n_strategy(self):
        """merge 策略：i18n JSON 文件自动 merge"""
        tmp_dir = tempfile.mkdtemp(prefix="e2e_merge_")
        try:
            # 预置 i18n 文件
            i18n_path = os.path.join(
                tmp_dir, "frontend/apps/web-antd/src/locales/langs/zh-CN/test.json",
            )
            os.makedirs(os.path.dirname(i18n_path), exist_ok=True)
            with open(i18n_path, "w", encoding="utf-8") as f:
                json.dump({"existing_key": "existing_value"}, f)

            writer = AtomicBatchWriter(tmp_dir)
            files = {
                "frontend/apps/web-antd/src/locales/langs/zh-CN/test.json": json.dumps(
                    {"new_key": "new_value"},
                ),
            }
            plan = writer.create_write_plan(
                files, conflict_action=ConflictAction.MERGE,
            )

            # i18n 文件应走 merge
            i18n_item = plan.items[0]
            assert i18n_item.action == WritePlanAction.MERGE

            result = writer.execute_write_plan(
                files, plan, conflict_action=ConflictAction.MERGE,
            )

            # 验证合并结果包含两个 key
            with open(i18n_path, encoding="utf-8") as f:
                merged = json.load(f)
            assert "existing_key" in merged
            assert "new_key" in merged
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# 3. 异常场景
# ============================================================


class TestErrorScenarios:
    """异常场景回归"""

    def test_cycle_dependency(self):
        """循环依赖检测"""
        project = BatchCrudProject(
            project_name="cycle-test",
            entities=[
                _entity("a", "a_table", [_field("b_id", "integer")]),
                _entity("b", "b_table", [_field("a_id", "integer")]),
            ],
            cross_relations=[
                EntityRelation(
                    source_entity="a",
                    target_entity="b",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="b_id",
                ),
                EntityRelation(
                    source_entity="b",
                    target_entity="a",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="a_id",
                ),
            ],
        )
        result = validate_and_sort(project)
        assert result.valid is False
        cycle_errors = [
            e for e in result.errors if "cycle" in e.code.value.lower()
        ]
        assert len(cycle_errors) >= 1

    def test_missing_entity_reference(self):
        """缺失实体引用"""
        project = BatchCrudProject(
            project_name="missing-ref",
            entities=[_entity("order", "orders", [_field("title")])],
            cross_relations=[
                EntityRelation(
                    source_entity="order",
                    target_entity="customer",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="customer_id",
                ),
            ],
        )
        result = validate_and_sort(project)
        assert result.valid is False
        missing = [
            e for e in result.errors if "missing" in e.code.value.lower()
        ]
        assert len(missing) >= 1

    def test_many_to_many_error(self):
        """many_to_many 直接使用 → 错误"""
        project = BatchCrudProject(
            project_name="m2m-test",
            entities=[
                _entity("user", "users", [_field("name")]),
                _entity("role", "roles", [_field("name")]),
            ],
            cross_relations=[
                EntityRelation(
                    source_entity="user",
                    target_entity="role",
                    relation_type=RelationType.MANY_TO_MANY,
                ),
            ],
        )
        result = validate_and_sort(project)
        assert result.valid is False
        m2m = [
            e for e in result.errors if "many_to_many" in e.code.value.lower()
        ]
        assert len(m2m) >= 1

    def test_self_reference_error(self):
        """自引用检测"""
        project = BatchCrudProject(
            project_name="self-ref",
            entities=[_entity("category", "categories", [_field("name")])],
            cross_relations=[
                EntityRelation(
                    source_entity="category",
                    target_entity="category",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="parent_id",
                ),
            ],
        )
        result = validate_and_sort(project)
        self_ref = [
            e for e in result.errors if "self" in e.code.value.lower()
        ]
        assert len(self_ref) >= 1

    def test_duplicate_module_error(self):
        """重复 module"""
        project = BatchCrudProject(
            project_name="dup-mod",
            entities=[
                _entity("order", "orders", [_field("title")]),
                _entity("order", "order_copies", [_field("name")]),
            ],
        )
        result = validate_and_sort(project)
        assert result.valid is False


# ============================================================
# 4. 追问协议
# ============================================================


class TestClarifyProtocol:
    """追问协议回归"""

    def test_missing_entities_triggers_clarify(self):
        result = detect_missing_info({"entities": []})
        assert result.needs_clarification is True
        assert result.blocking_count >= 1

    def test_m2m_without_join_triggers_clarify(self):
        result = detect_missing_info({
            "entities": [
                {"module": "user", "fields": [{"name": "x"}]},
                {"module": "role", "fields": [{"name": "x"}]},
            ],
            "cross_relations": [{
                "source_entity": "user",
                "target_entity": "role",
                "relation_type": "many_to_many",
            }],
        })
        assert result.needs_clarification is True
        m2m_q = [q for q in result.questions if "m2m" in q.id]
        assert len(m2m_q) >= 1

    def test_valid_project_no_clarify(self):
        project = make_order_system()
        d = project.model_dump(mode="json")
        result = detect_missing_info(d)
        assert result.needs_clarification is False


# ============================================================
# 5. 自检
# ============================================================


class TestSelfCheck:
    """生成后自检回归"""

    def test_self_check_pass(self):
        modules = ["order", "customer"]
        result = run_self_check(
            modules,
            router_content="import order\nimport customer\n",
            backend_router_content="from .order import router\nfrom .customer import router\n",
        )
        assert result.passed is True

    def test_self_check_missing_route(self):
        result = run_self_check(
            ["order", "customer"],
            router_content="import order\n",
        )
        assert result.passed is False
        assert result.error_count >= 1


# ============================================================
# 6. 快照 roundtrip
# ============================================================


class TestSnapshotRoundtrip:
    """快照导入/导出 roundtrip"""

    def test_export_import_roundtrip(self):
        project = make_order_system()
        exported = export_snapshot(project.model_dump(mode="json"))
        imported = import_snapshot(exported)

        assert imported.success is True
        assert imported.project is not None
        assert imported.project["project_name"] == "order-system"
        assert len(imported.project["entities"]) == 3

    def test_roundtrip_preserves_relations(self):
        project = make_user_role_system()
        exported = export_snapshot(project.model_dump(mode="json"))
        imported = import_snapshot(exported)

        assert imported.success is True
        assert len(imported.project["cross_relations"]) == 3


# ============================================================
# 7. Merge 增量合并
# ============================================================


class TestMergeIncremental:
    """增量合并回归"""

    def test_add_entity_via_merge(self):
        """通过 merge 添加新实体"""
        base = make_order_system()
        patch = BatchMergePatch(
            entities=[
                _entity("product", "products", [
                    _field("name"),
                    _field("price", "decimal"),
                ]),
            ],
        )
        result = merge_batch_project(base, patch)
        merged = result.project
        assert len(merged.entities) == 4
        modules = [e.module for e in merged.entities]
        assert "product" in modules

    def test_merge_preserves_existing(self):
        """merge 不丢失已有实体"""
        base = make_order_system()
        original_count = len(base.entities)

        patch = BatchMergePatch(
            entities=[
                _entity("customer", "customers", [
                    _field("name"),
                    _field("address", "text"),
                ]),
            ],
        )
        result = merge_batch_project(base, patch)
        merged = result.project
        assert len(merged.entities) == original_count


# ============================================================
# 8. Undo Bundle
# ============================================================


class TestUndoBundleE2E:
    """undo bundle 回归"""

    def test_generate_and_revert(self):
        """生成→导出 undo→回滚→文件恢复"""
        tmp_dir = tempfile.mkdtemp(prefix="e2e_undo_")
        try:
            # 预置文件
            existing_path = os.path.join(tmp_dir, "backend/app/models/order.py")
            os.makedirs(os.path.dirname(existing_path), exist_ok=True)
            with open(existing_path, "w", encoding="utf-8") as f:
                f.write("# original\nclass Order: pass\n")

            # 写盘
            writer = AtomicBatchWriter(tmp_dir)
            files = {
                "backend/app/models/order.py": "# generated\nclass Order:\n    NEW = True\n",
                "backend/app/models/customer.py": "class Customer: pass\n",
            }
            plan = writer.create_write_plan(
                files, conflict_action=ConflictAction.OVERWRITE,
            )
            result = writer.execute_write_plan(
                files, plan, conflict_action=ConflictAction.OVERWRITE,
            )
            assert len(result.written) >= 1

            # 构建 undo bundle
            written_records = []
            for path in result.written:
                action = "modified" if path == "backend/app/models/order.py" else "created"
                original = "# original\nclass Order: pass\n" if action == "modified" else None
                written_records.append({
                    "path": path,
                    "action": action,
                    "original_content": original,
                    "new_content": files.get(path, ""),
                })

            bundle = build_undo_bundle(tmp_dir, written_records, run_id="e2e_test")
            assert bundle.file_count() >= 1

            # 执行回滚
            def write_fn(path: str, content: str) -> None:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

            def delete_fn(path: str) -> None:
                if os.path.exists(path):
                    os.remove(path)

            revert_result = apply_revert(
                bundle, write_fn=write_fn, delete_fn=delete_fn,
            )
            assert revert_result.success is True

            # 验证：order.py 恢复原内容
            with open(existing_path, encoding="utf-8") as f:
                assert "# original" in f.read()

            # 验证：customer.py 被删除
            customer_path = os.path.join(tmp_dir, "backend/app/models/customer.py")
            assert not os.path.exists(customer_path)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# 9. 依赖排序正确性
# ============================================================


class TestDependencyOrdering:
    """依赖排序回归"""

    def test_auto_sort_order(self):
        """自动排序：父实体在子实体之前"""
        project = BatchCrudProject(
            project_name="auto-sort",
            entities=[
                _entity("order-item", "order_items", [_field("x")]),
                _entity("order", "orders", [_field("x")]),
                _entity("customer", "customers", [_field("x")]),
            ],
            cross_relations=[
                EntityRelation(
                    source_entity="order",
                    target_entity="customer",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="customer_id",
                ),
                EntityRelation(
                    source_entity="order-item",
                    target_entity="order",
                    relation_type=RelationType.BELONGS_TO,
                    foreign_key="order_id",
                ),
            ],
        )
        result = validate_and_sort(project)
        assert result.valid is True

        order = result.resolved_order
        assert order.index("customer") < order.index("order")
        assert order.index("order") < order.index("order-item")

    def test_explicit_order_validated(self):
        """显式 generation_order 与依赖一致时通过"""
        project = make_order_system()
        result = validate_and_sort(project)
        assert result.valid is True
        assert result.resolved_order == ["customer", "order", "order-item"]
