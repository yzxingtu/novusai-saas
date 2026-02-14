"""
批量写盘引擎 — 单元测试

覆盖：
- WritePlan 生成（create/update/merge/skip 四类 action）
- 原子写入：成功路径
- 回滚：中途失败不留半成品
- 模拟权限不足/只读/merge 冲突
- entity_file_map 按实体统计
- 幂等性：相同输入生成相同 WritePlan
"""

import json
import os
import stat
import tempfile

import pytest

from app.codegen.batch_writer import (
    AtomicBatchWriter,
    WritePlan,
    WritePlanAction,
    WritePlanReason,
)
from app.codegen.writer import ConflictAction


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def project_dir():
    """创建模拟项目目录结构"""
    import shutil
    d = tempfile.mkdtemp(prefix="crud_test_")
    root = os.path.join(d, "project")
    os.makedirs(os.path.join(root, "backend", "app", "models"), exist_ok=True)
    os.makedirs(os.path.join(root, "frontend", "apps", "web-antd", "src", "api"), exist_ok=True)
    os.makedirs(os.path.join(root, "frontend", "apps", "web-antd", "src", "locales", "langs", "zh-CN"), exist_ok=True)
    yield root
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def writer(project_dir):
    return AtomicBatchWriter(project_dir)


def _gen_files(
    model: bool = True,
    i18n: bool = False,
    ddl: bool = False,
) -> dict[str, str]:
    """生成测试文件集"""
    files: dict[str, str] = {}
    if model:
        files["backend/app/models/order.py"] = "class Order:\n    pass\n"
    if i18n:
        files["frontend/apps/web-antd/src/locales/langs/zh-CN/order.json"] = json.dumps(
            {"order": {"title": "订单"}}, ensure_ascii=False,
        )
    if ddl:
        files["__ddl_preview__.sql"] = "CREATE TABLE orders (...);"
    return files


# ============================================================
# WritePlan 生成
# ============================================================


class TestWritePlan:
    """WritePlan 生成测试"""

    def test_new_files_action_create(self, writer):
        """新文件的 action 应为 create"""
        files = _gen_files(model=True)
        plan = writer.create_write_plan(files)

        assert len(plan.items) == 1
        item = plan.items[0]
        assert item.action == WritePlanAction.CREATE
        assert item.reason == WritePlanReason.NEW_FILE
        assert not item.exists

    def test_existing_file_skip(self, writer, project_dir):
        """已存在文件 + SKIP 策略"""
        model_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        with open(model_path, "w", encoding="utf-8") as f:
            f.write("# old content")

        files = _gen_files(model=True)
        plan = writer.create_write_plan(files, conflict_action=ConflictAction.SKIP)

        item = plan.items[0]
        assert item.action == WritePlanAction.SKIP
        assert item.reason == WritePlanReason.CONFLICT_SKIP
        assert item.exists

    def test_existing_file_overwrite(self, writer, project_dir):
        """已存在文件 + OVERWRITE 策略"""
        model_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        with open(model_path, "w", encoding="utf-8") as f:
            f.write("# old content")

        files = _gen_files(model=True)
        plan = writer.create_write_plan(
            files, conflict_action=ConflictAction.OVERWRITE,
        )

        item = plan.items[0]
        assert item.action == WritePlanAction.UPDATE
        assert item.reason == WritePlanReason.CONFLICT_OVERWRITE

    def test_force_paths_overwrite(self, writer, project_dir):
        """force_paths 强制覆盖"""
        model_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        with open(model_path, "w", encoding="utf-8") as f:
            f.write("# old content")

        files = _gen_files(model=True)
        plan = writer.create_write_plan(
            files,
            conflict_action=ConflictAction.SKIP,
            force_paths={"backend/app/models/order.py"},
        )

        item = plan.items[0]
        assert item.action == WritePlanAction.UPDATE
        assert item.reason == WritePlanReason.FORCE_OVERWRITE

    def test_i18n_file_merge(self, writer, project_dir):
        """已存在 i18n 文件自动走 merge"""
        files = _gen_files(model=False, i18n=True)
        i18n_key = [k for k in files if k.endswith(".json")][0]

        abs_i18n = writer._abs_path(i18n_key)
        os.makedirs(os.path.dirname(abs_i18n), exist_ok=True)
        with open(abs_i18n, "w", encoding="utf-8") as f:
            json.dump({"existing": "value"}, f, ensure_ascii=False)

        plan = writer.create_write_plan(files)

        assert len(plan.items) == 1
        item = plan.items[0]
        assert item.action == WritePlanAction.MERGE
        assert item.reason == WritePlanReason.I18N_MERGE
        assert item.is_i18n

    def test_unsafe_path_skip(self, writer):
        """不安全路径被 skip"""
        files = {"../../etc/passwd": "malicious"}
        plan = writer.create_write_plan(files)

        assert len(plan.items) == 1
        item = plan.items[0]
        assert item.action == WritePlanAction.SKIP
        assert item.reason == WritePlanReason.UNSAFE_PATH

    def test_virtual_files_excluded(self, writer):
        """虚拟文件不出现在 plan 中"""
        files = _gen_files(ddl=True, model=True)
        plan = writer.create_write_plan(files)

        paths = [item.path for item in plan.items]
        assert "__ddl_preview__.sql" not in paths
        assert plan.ddl_preview == "CREATE TABLE orders (...);"

    def test_summary_counts(self, writer, project_dir):
        """统计正确"""
        model_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        with open(model_path, "w", encoding="utf-8") as f:
            f.write("# old")

        files = _gen_files(model=True, i18n=True)
        plan = writer.create_write_plan(files, conflict_action=ConflictAction.SKIP)

        # model: exists + skip, i18n: new → create
        assert plan.summary.skip_count == 1
        assert plan.summary.create_count == 1
        assert plan.summary.total_files == 2

    def test_entity_file_map_stats(self, writer):
        """entity_file_map 按实体统计"""
        files = _gen_files(model=True, i18n=True)
        entity_map = {
            "backend/app/models/order.py": "order",
        }
        plan = writer.create_write_plan(
            files, entity_file_map=entity_map,
        )

        # model 属于 order 实体
        model_item = next(
            i for i in plan.items if "models" in i.path
        )
        assert model_item.owner == "order"

        assert "order" in plan.summary.entity_stats
        assert plan.summary.entity_stats["order"]["create"] == 1

    def test_idempotent_plan(self, writer):
        """相同输入生成相同 WritePlan"""
        files = _gen_files(model=True, i18n=True)
        plan1 = writer.create_write_plan(files)
        plan2 = writer.create_write_plan(files)

        assert plan1.to_dict() == plan2.to_dict()


# ============================================================
# 原子写入 — 成功路径
# ============================================================


class TestAtomicWriteSuccess:
    """原子写入成功路径"""

    def test_create_new_files(self, writer, project_dir):
        """成功创建新文件"""
        files = _gen_files(model=True)
        plan = writer.create_write_plan(files)
        result = writer.execute_write_plan(files, plan)

        assert len(result.errors) == 0
        assert "backend/app/models/order.py" in result.written

        model_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        with open(model_path, "r", encoding="utf-8") as f:
            assert f.read() == "class Order:\n    pass\n"

    def test_overwrite_existing(self, writer, project_dir):
        """成功覆盖已存在文件"""
        model_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        with open(model_path, "w", encoding="utf-8") as f:
            f.write("# old")

        files = _gen_files(model=True)
        plan = writer.create_write_plan(
            files, conflict_action=ConflictAction.OVERWRITE,
        )
        result = writer.execute_write_plan(
            files, plan, conflict_action=ConflictAction.OVERWRITE,
        )

        assert len(result.errors) == 0
        with open(model_path, "r", encoding="utf-8") as f:
            assert f.read() == "class Order:\n    pass\n"

    def test_merge_i18n(self, writer, project_dir):
        """成功合并 i18n 文件"""
        i18n_rel = "frontend/apps/web-antd/src/locales/langs/zh-CN/order.json"
        i18n_abs = writer._abs_path(i18n_rel)
        os.makedirs(os.path.dirname(i18n_abs), exist_ok=True)
        with open(i18n_abs, "w", encoding="utf-8") as f:
            json.dump({"existing": "value"}, f, ensure_ascii=False)

        files = _gen_files(i18n=True)
        plan = writer.create_write_plan(files)
        result = writer.execute_write_plan(files, plan)

        assert len(result.errors) == 0
        with open(i18n_abs, "r", encoding="utf-8") as f:
            merged = json.load(f)
        assert merged["existing"] == "value"  # 保留旧值
        assert merged["order"]["title"] == "订单"  # 新增值

    def test_skip_existing(self, writer, project_dir):
        """skip 策略不修改文件"""
        model_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        with open(model_path, "w", encoding="utf-8") as f:
            f.write("# original")

        files = _gen_files(model=True)
        plan = writer.create_write_plan(
            files, conflict_action=ConflictAction.SKIP,
        )
        result = writer.execute_write_plan(
            files, plan, conflict_action=ConflictAction.SKIP,
        )

        assert "backend/app/models/order.py" in result.skipped
        with open(model_path, "r", encoding="utf-8") as f:
            assert f.read() == "# original"

    def test_ddl_preview_in_result(self, writer):
        """DDL 预览出现在结果中"""
        files = _gen_files(model=True, ddl=True)
        plan = writer.create_write_plan(files)
        result = writer.execute_write_plan(files, plan)

        assert result.ddl_preview == "CREATE TABLE orders (...);"


# ============================================================
# 回滚 — 失败路径
# ============================================================


class TestAtomicRollback:
    """原子回滚测试"""

    def test_rollback_on_write_failure(self, writer, project_dir):
        """写入失败时回滚已写入的文件"""
        files = {
            "backend/app/models/order.py": "class Order: pass\n",
            "backend/app/models/readonly/product.py": "class Product: pass\n",
        }

        # 创建只读目录
        readonly_dir = os.path.join(project_dir, "backend", "app", "models", "readonly")
        os.makedirs(readonly_dir, exist_ok=True)

        # 预创建一个同名文件并设只读
        readonly_file = os.path.join(readonly_dir, "product.py")
        with open(readonly_file, "w", encoding="utf-8") as f:
            f.write("# original")

        try:
            os.chmod(readonly_file, stat.S_IREAD)

            plan = writer.create_write_plan(
                files, conflict_action=ConflictAction.OVERWRITE,
            )
            result = writer.execute_write_plan(
                files, plan, conflict_action=ConflictAction.OVERWRITE,
            )

            assert len(result.errors) > 0
            assert len(result.written) == 0
        finally:
            os.chmod(readonly_file, stat.S_IWRITE | stat.S_IREAD)

    def test_no_partial_write_on_merge_failure(self, writer, project_dir):
        """合并失败时不留部分写入"""
        good_file = "backend/app/models/order.py"
        bad_i18n = "frontend/apps/web-antd/src/locales/langs/zh-CN/bad.json"

        bad_abs = writer._abs_path(bad_i18n)
        os.makedirs(os.path.dirname(bad_abs), exist_ok=True)
        with open(bad_abs, "w", encoding="utf-8") as f:
            f.write("NOT VALID JSON {{{")

        files = {
            good_file: "class Order: pass\n",
            bad_i18n: "NOT VALID JSON EITHER",
        }

        plan = writer.create_write_plan(files)
        result = writer.execute_write_plan(files, plan)

        assert len(result.errors) > 0
        order_path = os.path.join(project_dir, "backend", "app", "models", "order.py")
        assert not os.path.exists(order_path) or len(result.written) == 0


# ============================================================
# preview_and_plan 便捷入口
# ============================================================


class TestPreviewAndPlan:
    """preview_and_plan 便捷入口"""

    def test_returns_confirmation_structure(self, writer):
        files = _gen_files(model=True)
        output = writer.preview_and_plan(files)

        assert output["requires_confirmation"] is True
        assert "write_plan" in output
        assert "message" in output
        assert "1 new" in output["message"]

    def test_plan_in_output(self, writer):
        files = _gen_files(model=True, i18n=True)
        output = writer.preview_and_plan(files)

        plan = output["write_plan"]
        assert "items" in plan
        assert "summary" in plan
        assert plan["summary"]["total_files"] == 2


# ============================================================
# 文件类型分类
# ============================================================


class TestFileClassification:
    """文件类型分类测试"""

    def test_classify_model(self, writer):
        assert writer._classify_file("backend/app/models/order.py") == "model"

    def test_classify_schema(self, writer):
        assert writer._classify_file("backend/app/schemas/order.py") == "schema"

    def test_classify_i18n(self, writer):
        assert writer._classify_file("frontend/apps/web-antd/src/locales/zh.json") == "i18n"

    def test_classify_view(self, writer):
        assert writer._classify_file("frontend/apps/web-antd/src/views/order/index.vue") == "view"

    def test_classify_controller(self, writer):
        assert writer._classify_file("backend/app/api/admin/orders.py") == "controller"

    def test_classify_api_ts(self, writer):
        assert writer._classify_file("frontend/apps/web-antd/src/api/admin/orders.ts") == "api_ts"
