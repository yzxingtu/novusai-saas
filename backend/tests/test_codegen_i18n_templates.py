"""
CRUD Generator i18n + 测试脚手架模板渲染测试

验证:
- CrudGenerator._build_frontend_i18n_zh/en() → 合法 JSON dict
- CrudGenerator._build_backend_messages_zh/en() → 合法 JSON dict
- test_api.py.j2 → 合法 Python
"""

import ast
import json
import os
import re

from jinja2 import Environment, FileSystemLoader

from app.codegen.schemas import (
    CrudConfig,
    EnumDefinition,
    EnumOption,
    FieldConfig,
    FieldType,
    FormConfig,
    FormType,
    ListConfig,
    PermissionConfig,
    RelationConfig,
    RelationType,
    ScopeType,
    StateTransition,
)

# ---- Jinja2 环境 ----

BACKEND_TEMPLATE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "app", "codegen", "templates", "backend")
)


def _snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _capitalize(s: str) -> str:
    return s[0].upper() + s[1:] if s else s


def _make_env(template_dir: str) -> Environment:
    """Create Jinja2 env with all filters matching CrudGenerator._create_env()"""
    from app.codegen.generator import (
        _camel_filter,
        _capitalize_filter,
        _kebab_filter,
        _pascal_filter,
        _pluralize,
        _snake_filter,
    )

    env = Environment(
        loader=FileSystemLoader(template_dir),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["snake"] = _snake_filter
    env.filters["pascal"] = _pascal_filter
    env.filters["camel"] = _camel_filter
    env.filters["capitalize"] = _capitalize_filter
    env.filters["kebab"] = _kebab_filter
    env.filters["pluralize"] = _pluralize
    return env


backend_env = _make_env(BACKEND_TEMPLATE_DIR)


# ---- 测试配置 ----


def _build_order_config() -> CrudConfig:
    return CrudConfig(
        module="order",
        table_name="orders",
        display_name="订单",
        display_name_en="Order",
        scope=ScopeType.TENANT,
        parent_menu="business",
        description="订单管理模块",
        has_status_toggle=True,
        recyclable=True,
        fields=[
            FieldConfig(
                name="order_no",
                type=FieldType.STRING,
                label_zh="订单编号",
                label_en="Order No.",
                required=True,
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
                searchable=True,
            ),
            FieldConfig(
                name="remark",
                type=FieldType.TEXT,
                label_zh="备注",
                label_en="Remark",
                in_list=False,
            ),
            FieldConfig(
                name="is_urgent",
                type=FieldType.BOOLEAN,
                label_zh="是否加急",
                label_en="Urgent",
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
        list_config=ListConfig(default_sort="-created_at"),
        form_config=FormConfig(form_type=FormType.DRAWER),
        permissions=PermissionConfig(menu_icon="lucide:shopping-cart"),
    )


def _build_context(config: CrudConfig, scope: str = "tenant") -> dict:
    module_snake = config.module.replace("-", "_")
    model_class = "".join(w.capitalize() for w in module_snake.split("_"))
    return {
        "config": config,
        "model_class": model_class,
        "module": config.module,
        "module_snake": module_snake,
        "scope": scope,
        "scope_dir": scope,
        "table_name": config.table_name,
        "display_name": config.display_name,
        "description": config.description,
        "fields": config.fields,
        "relations": config.relations,
        "enums": config.enums,
        "has_status_toggle": config.has_status_toggle,
        "recyclable": config.recyclable,
        "parent_menu": config.parent_menu,
        "permissions": config.permissions,
        "hooks": config.hooks,
        "i18n_prefix": f"{scope}.{module_snake}",
    }


def _assert_valid_json(text: str, label: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        lines = text.split("\n")
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 2)
        context = "\n".join(
            f"{'>>>' if i + 1 == e.lineno else '   '} {i + 1}: {lines[i]}"
            for i in range(start, end)
        )
        raise AssertionError(
            f"[{label}] JSONDecodeError at line {e.lineno}: {e.msg}\n{context}"
        ) from None


def _assert_valid_python(code: str, label: str) -> None:
    try:
        ast.parse(code)
    except SyntaxError as e:
        lines = code.split("\n")
        start = max(0, e.lineno - 3)
        end = min(len(lines), e.lineno + 2)
        context = "\n".join(
            f"{'>>>' if i + 1 == e.lineno else '   '} {i + 1}: {lines[i]}"
            for i in range(start, end)
        )
        raise AssertionError(
            f"[{label}] SyntaxError at line {e.lineno}: {e.msg}\n{context}"
        ) from None


# ---- Tests ----


def test_frontend_i18n_zh():
    """Test inline _build_frontend_i18n_zh produces valid i18n dict"""
    from app.codegen.generator import CrudGenerator

    config = _build_order_config()
    data = CrudGenerator._build_frontend_i18n_zh(config)

    assert "title" in data
    assert "field" in data
    assert "order_no" in data["field"]
    assert data["field"]["order_no"] == "订单编号"
    assert "messages" in data
    assert "createSuccess" in data["messages"]
    # Verify JSON serializable
    json.dumps(data, ensure_ascii=False)
    print("✅ _build_frontend_i18n_zh OK")


def test_backend_messages_zh():
    """Test inline _build_backend_messages_zh produces valid i18n dict"""
    from app.codegen.generator import CrudGenerator

    config = _build_order_config()
    data = CrudGenerator._build_backend_messages_zh(config)

    assert "order" in data
    order = data["order"]
    assert "not_found" in order
    assert "created" in order
    assert "error" in order
    assert "not_found" in order["error"]
    assert "field" in order
    assert "order_no" in order["field"]
    assert order["field"]["order_no"] == "订单编号"
    # Verify JSON serializable
    json.dumps(data, ensure_ascii=False)
    print("✅ _build_backend_messages_zh OK")


def test_test_api_py():
    config = _build_order_config()
    ctx = _build_context(config)
    tmpl = backend_env.get_template("test_api.py.j2")
    code = tmpl.render(**ctx)
    _assert_valid_python(code, "test_api.py.j2")

    assert "class TestTenantOrder(BaseAPITest)" in code
    assert "/tenant/business/orders" in code
    assert "test_list" in code
    assert "test_create" in code
    assert "test_detail" in code
    assert "test_update" in code
    assert "test_delete" in code
    assert '"order_no"' in code
    assert '"amount"' in code
    assert '"status"' in code
    assert '"draft"' in code
    assert '"customer_id"' in code
    print("✅ test_api.py.j2 OK")


def test_admin_scope_messages():
    """scope=admin 时后端 messages 也正常"""
    from app.codegen.generator import CrudGenerator

    config = CrudConfig(
        module="setting",
        table_name="settings",
        display_name="系统设置",
        display_name_en="Setting",
        scope=ScopeType.ADMIN,
        parent_menu="system",
        has_status_toggle=False,
        fields=[
            FieldConfig(name="key", type=FieldType.STRING, label_zh="键", label_en="Key", required=True, max_length=100),
            FieldConfig(name="value", type=FieldType.TEXT, label_zh="值", label_en="Value"),
        ],
    )
    ctx = _build_context(config, scope="admin")

    data = CrudGenerator._build_backend_messages_zh(config)
    assert "setting" in data
    json.dumps(data, ensure_ascii=False)

    tmpl2 = backend_env.get_template("test_api.py.j2")
    code = tmpl2.render(**ctx)
    _assert_valid_python(code, "test_api.py.j2 (admin)")
    assert "class TestAdminSetting(BaseAPITest)" in code
    assert "/admin/system/settings" in code

    print("✅ admin scope i18n + test OK")


if __name__ == "__main__":
    test_frontend_i18n_zh()
    test_backend_messages_zh()
    test_test_api_py()
    test_admin_scope_messages()
    print("\n🎉 All 4 i18n/test template tests passed!")
