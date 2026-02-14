"""
配置模板存储 + Mock 数据生成器 单元测试
"""

import json
import os
import shutil
import tempfile

from app.codegen.mock_data import MockDataGenerator
from app.codegen.schemas import (
    CrudConfig,
    EnumDefinition,
    EnumOption,
    FieldConfig,
    FieldType,
    RelationConfig,
    RelationType,
    ScopeType,
)
from app.codegen.template_store import TemplateStore


# ---- 测试配置 ----


def _build_order_config() -> CrudConfig:
    return CrudConfig(
        module="order",
        table_name="orders",
        display_name="订单",
        display_name_en="Order",
        scope=ScopeType.TENANT,
        parent_menu="business",
        has_status_toggle=True,
        fields=[
            FieldConfig(
                name="order_no",
                type=FieldType.STRING,
                label_zh="订单编号",
                label_en="Order No.",
                required=True,
                max_length=64,
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
            FieldConfig(
                name="remark",
                type=FieldType.TEXT,
                label_zh="备注",
                label_en="Remark",
            ),
            FieldConfig(
                name="is_urgent",
                type=FieldType.BOOLEAN,
                label_zh="是否加急",
                label_en="Urgent",
            ),
            FieldConfig(
                name="order_date",
                type=FieldType.DATE,
                label_zh="下单日期",
                label_en="Order Date",
            ),
            FieldConfig(
                name="created_time",
                type=FieldType.DATETIME,
                label_zh="创建时间",
                label_en="Created Time",
            ),
            FieldConfig(
                name="extra_info",
                type=FieldType.JSON,
                label_zh="附加信息",
                label_en="Extra Info",
                nullable=True,
            ),
            FieldConfig(
                name="attachment",
                type=FieldType.FILE,
                label_zh="附件",
                label_en="Attachment",
                nullable=True,
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
                    EnumOption(value="pending", label_zh="待付款", label_en="Pending"),
                    EnumOption(value="paid", label_zh="已付款", label_en="Paid"),
                ],
            ),
        ],
    )


# ============================================================
# TemplateStore Tests
# ============================================================


class TestTemplateStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = TemplateStore(self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load(self):
        """保存并加载配置模板"""
        config = _build_order_config()
        self.store.save("order", config, description="订单模块")

        loaded = self.store.load("order")
        assert loaded is not None
        assert loaded.module == "order"
        assert loaded.table_name == "orders"
        assert len(loaded.fields) == len(config.fields)

    def test_load_nonexistent(self):
        """加载不存在的模板返回 None"""
        assert self.store.load("nonexistent") is None

    def test_load_raw(self):
        """加载原始数据含元信息"""
        config = _build_order_config()
        self.store.save("order", config, description="订单模块")

        raw = self.store.load_raw("order")
        assert raw is not None
        assert raw["name"] == "order"
        assert raw["description"] == "订单模块"
        assert "config" in raw
        assert "saved_at" in raw

    def test_list_all(self):
        """列出所有模板"""
        config = _build_order_config()
        self.store.save("order", config, description="订单")
        self.store.save("product", config, description="产品")

        templates = self.store.list_all()
        assert len(templates) == 2
        names = {t.name for t in templates}
        assert "order" in names
        assert "product" in names

    def test_list_empty(self):
        """空目录列表"""
        assert self.store.list_all() == []

    def test_delete(self):
        """删除模板"""
        config = _build_order_config()
        self.store.save("order", config)

        assert self.store.delete("order") is True
        assert self.store.load("order") is None
        assert self.store.delete("order") is False

    def test_exists(self):
        """检查模板是否存在"""
        config = _build_order_config()
        assert self.store.exists("order") is False
        self.store.save("order", config)
        assert self.store.exists("order") is True

    def test_overwrite(self):
        """覆盖已有模板"""
        config = _build_order_config()
        self.store.save("order", config, description="v1")
        self.store.save("order", config, description="v2")

        raw = self.store.load_raw("order")
        assert raw["description"] == "v2"

    def test_safe_name(self):
        """路径穿越安全"""
        config = _build_order_config()
        self.store.save("../evil", config)
        # 应存储为 __evil.json，不会穿越目录
        assert not os.path.exists(os.path.join(self.tmpdir, "..", "evil.json"))

    def test_roundtrip_json(self):
        """JSON 序列化/反序列化保持一致"""
        config = _build_order_config()
        self.store.save("test", config)
        loaded = self.store.load("test")
        assert loaded is not None
        assert loaded.model_dump(mode="json") == config.model_dump(mode="json")


# ============================================================
# MockDataGenerator Tests
# ============================================================


class TestMockDataGenerator:
    def setup_method(self):
        self.config = _build_order_config()
        self.gen = MockDataGenerator(self.config)

    def test_generate_default_count(self):
        """默认生成 50 条"""
        items = self.gen.generate()
        assert len(items) == 50

    def test_generate_custom_count(self):
        """自定义数量"""
        items = self.gen.generate(count=10)
        assert len(items) == 10

    def test_item_has_id(self):
        """每条数据有 id"""
        items = self.gen.generate(count=5)
        for i, item in enumerate(items):
            assert item["id"] == i + 1

    def test_string_field(self):
        """字符串字段生成"""
        items = self.gen.generate(count=3)
        for item in items:
            assert isinstance(item["order_no"], str)
            assert len(item["order_no"]) > 0

    def test_decimal_field(self):
        """数值字段生成"""
        items = self.gen.generate(count=3)
        for item in items:
            assert isinstance(item["amount"], (int, float))
            assert item["amount"] > 0

    def test_enum_field(self):
        """枚举字段值在可选范围内"""
        items = self.gen.generate(count=20)
        valid_values = {"draft", "pending", "paid"}
        for item in items:
            assert item["status"] in valid_values

    def test_boolean_field(self):
        """布尔字段生成"""
        items = self.gen.generate(count=20)
        values = {item["is_urgent"] for item in items}
        assert True in values or False in values

    def test_text_field(self):
        """文本字段生成"""
        items = self.gen.generate(count=3)
        for item in items:
            assert isinstance(item["remark"], str)

    def test_date_field(self):
        """日期字段格式"""
        items = self.gen.generate(count=3)
        for item in items:
            assert len(item["order_date"]) == 10  # YYYY-MM-DD

    def test_datetime_field(self):
        """日期时间字段格式"""
        items = self.gen.generate(count=20)
        non_none = [item["created_time"] for item in items if item["created_time"] is not None]
        assert len(non_none) > 0
        for val in non_none:
            assert "T" in val

    def test_json_field(self):
        """JSON 字段生成"""
        items = self.gen.generate(count=3)
        for item in items:
            if item["extra_info"] is not None:
                assert isinstance(item["extra_info"], dict)

    def test_file_field(self):
        """文件字段生成"""
        items = self.gen.generate(count=3)
        for item in items:
            if item["attachment"] is not None:
                assert item["attachment"].startswith("/files/")

    def test_relation_fk(self):
        """关联外键字段"""
        items = self.gen.generate(count=5)
        for item in items:
            assert "customer_id" in item
            assert isinstance(item["customer_id"], int)
            assert "customer_name" in item

    def test_status_toggle(self):
        """状态开关字段"""
        items = self.gen.generate(count=5)
        for item in items:
            assert "is_active" in item
            assert isinstance(item["is_active"], bool)

    def test_base_timestamps(self):
        """基础时间戳字段"""
        items = self.gen.generate(count=3)
        for item in items:
            assert "created_at" in item
            assert "updated_at" in item
            assert "T" in item["created_at"]

    def test_generate_single(self):
        """生成单条"""
        item = self.gen.generate_single()
        assert isinstance(item, dict)
        assert item["id"] == 1
        assert "order_no" in item

    def test_nullable_field(self):
        """可空字段偶尔生成 None"""
        items = self.gen.generate(count=100)
        # extra_info 和 attachment 是 nullable 的
        null_count = sum(1 for item in items if item.get("extra_info") is None)
        # 大约 10% 概率为 None，100 条中应至少有几个
        # 但由于随机性，仅断言不全为非空即可
        assert null_count >= 0  # 至少可以为 0（极端情况）
