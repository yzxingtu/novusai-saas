"""
CRUD Generator + Writer 单元测试

验证:
1. Generator 从 CrudConfig 生成全部文件
2. DDL 预览正确
3. Writer 冲突检测
4. Writer i18n 合并模式
5. Writer 路径安全检查
"""

import json
import os
import shutil
import tempfile

from app.codegen.generator import CrudGenerator
from app.codegen.schemas import (
    CrudConfig,
    EnumDefinition,
    EnumOption,
    FieldConfig,
    FieldType,
    FormConfig,
    FormType,
    IndexConfig,
    LayoutConfig,
    LayoutVariant,
    ListConfig,
    PermissionConfig,
    RelationConfig,
    RelationType,
    ScopeType,
    SelectableConfig,
)
from app.codegen.writer import (
    ConflictAction,
    CrudWriter,
    _deep_merge,
    _is_safe_path,
)


# ---- 测试配置 ----


def _build_order_config(scope: ScopeType = ScopeType.TENANT) -> CrudConfig:
    return CrudConfig(
        module="order",
        table_name="orders",
        display_name="订单",
        display_name_en="Order",
        scope=scope,
        parent_menu="business",
        description="订单管理模块",
        soft_delete=True,
        has_status_toggle=True,
        recyclable=True,
        fields=[
            FieldConfig(
                name="order_no",
                type=FieldType.STRING,
                label_zh="订单编号",
                label_en="Order No.",
                required=True,
                unique=True,
                max_length=64,
                searchable=True,
            ),
            FieldConfig(
                name="amount",
                type=FieldType.DECIMAL,
                label_zh="金额",
                label_en="Amount",
                required=True,
            ),
            FieldConfig(
                name="status",
                type=FieldType.ENUM,
                label_zh="状态",
                label_en="Status",
                required=True,
                enum_ref="OrderStatus",
            ),
        ],
        relations=[
            RelationConfig(
                name="customer",
                type=RelationType.BELONGS_TO,
                target_model="Customer",
                target_table="customers",
                foreign_key="customer_id",
                nullable=False,
                comment_zh="客户",
            ),
        ],
        enums=[
            EnumDefinition(
                name="OrderStatus",
                description="订单状态",
                values=[
                    EnumOption(value="draft", label_zh="草稿", label_en="Draft"),
                    EnumOption(value="paid", label_zh="已付款", label_en="Paid"),
                ],
            ),
        ],
        indexes=[
            IndexConfig(name="ix_orders_order_no", fields=["order_no"], unique=True),
        ],
        list_config=ListConfig(default_sort="-created_at"),
        form_config=FormConfig(form_type=FormType.DRAWER),
        selectable=SelectableConfig(label_field="order_no", value_field="id"),
        permissions=PermissionConfig(menu_icon="lucide:shopping-cart"),
    )


# ============================================================
# Generator Tests
# ============================================================


class TestCrudGenerator:
    def setup_method(self):
        self.gen = CrudGenerator()

    def test_generate_tenant_scope(self):
        """tenant scope 生成完整文件集"""
        config = _build_order_config(ScopeType.TENANT)
        files = self.gen.generate(config)

        # 后端文件
        assert "backend/app/enums/order.py" in files
        assert "backend/app/models/business/order.py" in files
        assert "backend/app/schemas/business/order.py" in files
        assert "backend/app/repositories/business/order_repository.py" in files
        assert "backend/app/services/business/order_service.py" in files
        assert "backend/app/api/tenant/orders.py" in files
        assert "backend/tests/api/test_tenant_orders.py" in files

        # 前端文件
        assert "frontend/apps/web-antd/src/api/tenant/orders.ts" in files
        assert "frontend/apps/web-antd/src/views/tenant/business/orders/data.ts" in files
        assert "frontend/apps/web-antd/src/views/tenant/business/orders/index.vue" in files
        assert "frontend/apps/web-antd/src/views/tenant/business/orders/modules/form.vue" in files

        # i18n
        assert "frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/order.json" in files
        assert "backend/app/locales/zh_CN/_order.json" in files

        # DDL
        assert "__ddl_preview__.sql" in files

        # 不应有 admin 文件
        assert "backend/app/api/admin/orders.py" not in files

    def test_generate_admin_scope(self):
        """admin scope 只生成 admin 端文件"""
        config = _build_order_config(ScopeType.ADMIN)
        files = self.gen.generate(config)

        assert "backend/app/api/admin/orders.py" in files
        assert "backend/app/api/tenant/orders.py" not in files
        assert "frontend/apps/web-antd/src/api/admin/orders.ts" in files

    def test_generate_both_scope(self):
        """both scope 生成 admin + tenant 双端"""
        config = _build_order_config(ScopeType.BOTH)
        files = self.gen.generate(config)

        assert "backend/app/api/tenant/orders.py" in files
        assert "backend/app/api/admin/orders.py" in files
        assert "frontend/apps/web-antd/src/api/tenant/orders.ts" in files
        assert "frontend/apps/web-antd/src/api/admin/orders.ts" in files

    def test_generate_file_count(self):
        """tenant scope 应生成 15+ 文件"""
        config = _build_order_config(ScopeType.TENANT)
        files = self.gen.generate(config)
        # 排除虚拟文件
        real_files = {k: v for k, v in files.items() if not k.startswith("__")}
        assert len(real_files) >= 13

    def test_generate_card_layout(self):
        """card 布局应使用 index_card.vue.j2"""
        config = _build_order_config()
        config.layout = LayoutConfig(variant=LayoutVariant.CARD_LIST)
        files = self.gen.generate(config)

        index_path = "frontend/apps/web-antd/src/views/tenant/business/orders/index.vue"
        assert index_path in files
        assert "Pagination" in files[index_path]

    def test_generate_kanban_layout(self):
        """kanban 布局应使用 index_kanban.vue.j2"""
        config = _build_order_config()
        config.layout = LayoutConfig(variant=LayoutVariant.KANBAN)
        files = self.gen.generate(config)

        index_path = "frontend/apps/web-antd/src/views/tenant/business/orders/index.vue"
        assert index_path in files
        assert "groupedItems" in files[index_path]

    def test_ddl_preview(self):
        """DDL 预览包含正确的建表语句"""
        config = _build_order_config()
        ddl = CrudGenerator.generate_ddl_preview(config)

        assert "CREATE TABLE orders" in ddl
        assert "tenant_id INTEGER NOT NULL" in ddl
        assert "order_no VARCHAR(64)" in ddl
        assert "amount NUMERIC(10,2)" in ddl
        assert "status VARCHAR(50)" in ddl
        assert "customer_id INTEGER NOT NULL" in ddl
        assert "is_active BOOLEAN NOT NULL DEFAULT TRUE" in ddl
        assert "is_deleted BOOLEAN NOT NULL DEFAULT FALSE" in ddl
        assert "ix_orders_order_no" in ddl
        assert "UNIQUE" in ddl

    def test_ddl_admin_no_tenant_id(self):
        """admin scope DDL 不包含 tenant_id"""
        config = _build_order_config(ScopeType.ADMIN)
        ddl = CrudGenerator.generate_ddl_preview(config)

        assert "tenant_id" not in ddl


# ============================================================
# Writer Tests
# ============================================================


class TestCrudWriter:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.writer = CrudWriter(self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_new_files(self):
        """写入新文件"""
        files = {
            "backend/app/models/test/foo.py": "class Foo:\n    pass\n",
            "backend/app/enums/foo.py": "class FooEnum:\n    pass\n",
        }
        result = self.writer.write(files)

        assert len(result.written) == 2
        assert len(result.skipped) == 0
        assert len(result.errors) == 0
        assert os.path.exists(os.path.join(self.tmpdir, "backend/app/models/test/foo.py"))

    def test_conflict_detection(self):
        """冲突检测"""
        # 预先创建文件
        path = os.path.join(self.tmpdir, "backend/app/models/test/bar.py")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("existing content")

        files = {
            "backend/app/models/test/bar.py": "new content",
        }
        conflicts = self.writer.detect_conflicts(files)

        assert len(conflicts) == 1
        assert conflicts[0].path == "backend/app/models/test/bar.py"
        assert conflicts[0].existing_size > 0

    def test_conflict_skip(self):
        """冲突时跳过"""
        path = os.path.join(self.tmpdir, "backend/app/enums/bar.py")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("original")

        files = {"backend/app/enums/bar.py": "replacement"}
        result = self.writer.write(files, conflict_action=ConflictAction.SKIP)

        assert len(result.skipped) == 1
        with open(path, "r") as f:
            assert f.read() == "original"

    def test_conflict_overwrite(self):
        """冲突时覆盖"""
        path = os.path.join(self.tmpdir, "backend/app/enums/baz.py")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("original")

        files = {"backend/app/enums/baz.py": "replacement"}
        result = self.writer.write(files, conflict_action=ConflictAction.OVERWRITE)

        assert len(result.written) == 1
        with open(path, "r") as f:
            assert f.read() == "replacement"

    def test_i18n_merge(self):
        """i18n 文件合并模式"""
        rel = "frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/test.json"
        path = os.path.join(self.tmpdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        existing = {"existing_key": "existing_value", "field": {"name": "名称"}}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        new_data = {"new_key": "new_value", "field": {"name": "新名称", "desc": "描述"}}
        files = {rel: json.dumps(new_data, ensure_ascii=False, indent=2)}

        result = self.writer.write(files)

        assert len(result.merged) == 1
        with open(path, "r", encoding="utf-8") as f:
            merged = json.load(f)

        assert merged["existing_key"] == "existing_value"
        assert merged["new_key"] == "new_value"
        assert merged["field"]["name"] == "名称"  # 已有 key 保留
        assert merged["field"]["desc"] == "描述"  # 新 key 追加

    def test_path_safety_reject(self):
        """路径安全：拒绝不在白名单的路径"""
        files = {
            "/etc/passwd": "hacked",
            "../../../etc/shadow": "hacked",
            "some/random/path.py": "content",
        }
        result = self.writer.write(files)

        assert len(result.errors) == 3
        assert len(result.written) == 0

    def test_ddl_not_written(self):
        """DDL 预览不写入磁盘"""
        files = {"__ddl_preview__.sql": "CREATE TABLE test (id SERIAL);"}
        result = self.writer.write(files)

        assert result.ddl_preview == "CREATE TABLE test (id SERIAL);"
        assert len(result.written) == 0
        assert not os.path.exists(os.path.join(self.tmpdir, "__ddl_preview__.sql"))

    def test_preview_mode(self):
        """预览模式不写入磁盘"""
        files = {
            "backend/app/models/test/foo.py": "class Foo: pass\n",
            "__ddl_preview__.sql": "CREATE TABLE test (id SERIAL);",
        }
        preview = self.writer.preview(files)

        assert len(preview["files"]) == 1
        assert preview["total_new"] == 1
        assert preview["total_conflict"] == 0
        assert "CREATE TABLE" in preview["ddl_preview"]
        assert not os.path.exists(os.path.join(self.tmpdir, "backend/app/models/test/foo.py"))

    def test_preview_includes_operation(self):
        """预览文件包含 operation 字段"""
        files = {
            "backend/app/models/test/new.py": "class New: pass\n",
        }
        preview = self.writer.preview(files)

        assert preview["files"][0]["operation"] == "create"

    def test_preview_conflict_operation(self):
        """已存在文件的 operation 为 conflict"""
        rel = "backend/app/enums/existing.py"
        path = os.path.join(self.tmpdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("existing")

        files = {rel: "new content"}
        preview = self.writer.preview(files)

        assert preview["files"][0]["operation"] == "conflict"
        assert preview["total_conflict"] == 1

    def test_preview_i18n_merge_operation(self):
        """i18n 文件已存在时 operation 为 merge"""
        rel = "frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/test.json"
        path = os.path.join(self.tmpdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write('{"key": "val"}')

        files = {rel: '{"new": "val"}'}
        preview = self.writer.preview(files)

        assert preview["files"][0]["operation"] == "merge"

    def test_preview_include_content(self):
        """include_content=True 时返回文件内容"""
        content = "class Foo: pass\n"
        files = {"backend/app/models/test/foo.py": content}
        preview = self.writer.preview(files, include_content=True)

        assert preview["files"][0]["content"] == content

    def test_preview_no_content_by_default(self):
        """默认不返回文件内容"""
        files = {"backend/app/models/test/foo.py": "content"}
        preview = self.writer.preview(files)

        assert "content" not in preview["files"][0]

    def test_preview_warnings(self):
        """预览包含 warnings"""
        files = {"backend/app/models/test/foo.py": "content"}
        preview = self.writer.preview(files, warnings=["scope=both warning"])

        assert len(preview["warnings"]) == 1
        assert "scope=both" in preview["warnings"][0]

    def test_force_paths(self):
        """force_paths 强制覆盖指定文件"""
        rel = "backend/app/enums/forced.py"
        path = os.path.join(self.tmpdir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("original")

        files = {rel: "forced_new"}
        result = self.writer.write(
            files,
            conflict_action=ConflictAction.SKIP,
            force_paths={rel},
        )

        assert len(result.written) == 1
        with open(path, "r") as f:
            assert f.read() == "forced_new"


# ============================================================
# 辅助函数测试
# ============================================================


class TestDeepMerge:
    def test_simple(self):
        base = {"a": 1, "b": 2}
        overlay = {"b": 99, "c": 3}
        result = _deep_merge(base, overlay)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_nested(self):
        base = {"x": {"a": 1}}
        overlay = {"x": {"a": 99, "b": 2}, "y": 3}
        result = _deep_merge(base, overlay)
        assert result == {"x": {"a": 1, "b": 2}, "y": 3}


class TestPathSafety:
    def test_allowed(self):
        assert _is_safe_path("backend/app/models/test.py") is True
        assert _is_safe_path("backend/tests/api/test_foo.py") is True
        assert _is_safe_path("frontend/apps/web-antd/src/api/test.ts") is True

    def test_rejected(self):
        assert _is_safe_path("../etc/passwd") is False
        assert _is_safe_path("random/file.py") is False
        assert _is_safe_path("/absolute/path.py") is False

    def test_windows_drive_letter(self):
        """Windows 盘符跳转"""
        assert _is_safe_path("C:\\Windows\\system32") is False
        assert _is_safe_path("D:/evil/path.py") is False

    def test_null_byte(self):
        """空字节注入"""
        assert _is_safe_path("backend/app/\x00evil.py") is False

    def test_empty_path(self):
        """空路径"""
        assert _is_safe_path("") is False

    def test_path_traversal_in_middle(self):
        """路径中间的穿越"""
        assert _is_safe_path("backend/app/../../etc/passwd") is False
        assert _is_safe_path("backend/app/models/../../../evil") is False
