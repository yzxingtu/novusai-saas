"""
CRUD Generator Jinja2 后端模板渲染测试

验证 6 个后端模板的渲染输出是否为合法 Python 语法
"""

import ast
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
    FormGroup,
    FormType,
    ImportExportConfig,
    IndexConfig,
    ListConfig,
    ListRenderPreset,
    PermissionConfig,
    PermissionAction,
    RelationConfig,
    RelationType,
    ScopeType,
    SearchConfig,
    SearchFieldConfig,
    SearchOperator,
    SearchComponent,
    SelectableConfig,
    StateTransition,
    UploadFieldConfig,
    ValidationRule,
)

# ---- Jinja2 环境 ----

TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "app",
    "codegen",
    "templates",
    "backend",
)


def _snake(name: str) -> str:
    """PascalCase → snake_case"""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _setup_env(template_dir: str) -> Environment:
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
        loader=FileSystemLoader(os.path.abspath(template_dir)),
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


env = _setup_env(TEMPLATE_DIR)


# ---- 测试配置 ----


def _build_order_config() -> CrudConfig:
    """订单模块完整配置"""
    return CrudConfig(
        module="order",
        table_name="orders",
        display_name="订单",
        display_name_en="Order",
        scope=ScopeType.TENANT,
        parent_menu="business",
        description="订单管理模块",
        soft_delete=True,
        has_status_toggle=True,
        recyclable=True,
        drag_sort=False,
        fields=[
            FieldConfig(
                name="order_no",
                type=FieldType.STRING,
                label_zh="订单编号",
                label_en="Order No.",
                required=True,
                unique=True,
                max_length=64,
                index=True,
                searchable=True,
                sortable=True,
                list_render=ListRenderPreset.COPY,
                form_rules=[
                    ValidationRule(type="regex", value=r"^[A-Z]{2}-\d{6}$"),
                ],
            ),
            FieldConfig(
                name="customer_name",
                type=FieldType.STRING,
                label_zh="客户名称",
                label_en="Customer Name",
                required=True,
                max_length=128,
                searchable=True,
            ),
            FieldConfig(
                name="amount",
                type=FieldType.DECIMAL,
                label_zh="金额",
                label_en="Amount",
                required=True,
                sortable=True,
                list_render=ListRenderPreset.MONEY,
            ),
            FieldConfig(
                name="status",
                type=FieldType.ENUM,
                label_zh="状态",
                label_en="Status",
                required=True,
                enum_ref="OrderStatus",
                searchable=True,
                list_render=ListRenderPreset.TAG,
            ),
            FieldConfig(
                name="remark",
                type=FieldType.TEXT,
                label_zh="备注",
                label_en="Remark",
                in_list=False,
            ),
            FieldConfig(
                name="config",
                type=FieldType.JSON,
                label_zh="配置",
                label_en="Config",
                in_list=False,
            ),
            FieldConfig(
                name="is_urgent",
                type=FieldType.BOOLEAN,
                label_zh="是否加急",
                label_en="Urgent",
                default=False,
            ),
            FieldConfig(
                name="order_date",
                type=FieldType.DATE,
                label_zh="下单日期",
                label_en="Order Date",
            ),
            FieldConfig(
                name="shipped_at",
                type=FieldType.DATETIME,
                label_zh="发货时间",
                label_en="Shipped At",
                in_list=False,
            ),
            FieldConfig(
                name="quantity",
                type=FieldType.INTEGER,
                label_zh="数量",
                label_en="Quantity",
                required=True,
                sortable=True,
            ),
            FieldConfig(
                name="weight",
                type=FieldType.FLOAT,
                label_zh="重量",
                label_en="Weight",
            ),
            FieldConfig(
                name="attachment",
                type=FieldType.FILE,
                label_zh="附件",
                label_en="Attachment",
                in_list=False,
                upload=UploadFieldConfig(max_count=5),
            ),
            FieldConfig(
                name="avatar",
                type=FieldType.FILE,
                label_zh="头像",
                label_en="Avatar",
                in_list=False,
                upload=UploadFieldConfig(upload_type="avatar", max_count=1),
            ),
        ],
        relations=[
            RelationConfig(
                name="customer",
                type=RelationType.BELONGS_TO,
                target_model="Customer",
                target_table="customers",
                foreign_key="customer_id",
                label_field="name",
                comment_zh="客户",
            ),
            RelationConfig(
                name="items",
                type=RelationType.HAS_MANY,
                target_model="OrderItem",
                target_table="order_items",
                cascade_delete=True,
                comment_zh="订单明细",
            ),
        ],
        search_config=SearchConfig(
            fields=[
                SearchFieldConfig(field="order_no", operator=SearchOperator.ILIKE),
                SearchFieldConfig(
                    field="status",
                    operator=SearchOperator.EQ,
                    component=SearchComponent.SELECT,
                    options_enum="OrderStatus",
                ),
            ],
        ),
        enums=[
            EnumDefinition(
                name="OrderStatus",
                description="订单状态",
                values=[
                    EnumOption(value="draft", label_zh="草稿", label_en="Draft"),
                    EnumOption(value="pending", label_zh="待付款", label_en="Pending"),
                    EnumOption(value="paid", label_zh="已付款", label_en="Paid"),
                    EnumOption(value="cancelled", label_zh="已取消", label_en="Cancelled"),
                ],
                transitions=[
                    StateTransition(
                        from_state="draft", to_state="pending",
                        action="submit", label_zh="提交", label_en="Submit",
                    ),
                    StateTransition(
                        from_state="draft", to_state="cancelled",
                        action="cancel", label_zh="取消", label_en="Cancel",
                    ),
                    StateTransition(
                        from_state="pending", to_state="paid",
                        action="pay", label_zh="付款", label_en="Pay",
                    ),
                    StateTransition(
                        from_state="pending", to_state="cancelled",
                        action="cancel", label_zh="取消", label_en="Cancel",
                    ),
                ],
            ),
        ],
        list_config=ListConfig(default_sort="-created_at"),
        form_config=FormConfig(
            form_type=FormType.DRAWER,
            groups=[
                FormGroup(
                    title_zh="基本信息",
                    title_en="Basic Info",
                    fields=["order_no", "customer_name", "amount", "status"],
                ),
            ],
        ),
        selectable=SelectableConfig(
            label_field="order_no",
            value_field="id",
            search_fields=["order_no", "customer_name"],
        ),
        indexes=[
            IndexConfig(fields=["tenant_id", "status"]),
            IndexConfig(fields=["tenant_id", "order_no"], unique=True),
        ],
        permissions=PermissionConfig(
            actions=["read", "create", "update", "delete"],
            extra_actions=[
                PermissionAction(code="ship", label_zh="发货", label_en="Ship"),
            ],
            menu_icon="lucide:shopping-cart",
            menu_sort_order=10,
        ),
        hooks=["before_create", "after_create", "before_delete"],
    )


def _build_context(config: CrudConfig, scope: str = "tenant") -> dict:
    """构建模板渲染上下文"""
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
        "display_name_en": config.display_name_en,
        "description": config.description,
        "fields": config.fields,
        "relations": config.relations,
        "enums": config.enums,
        "selectable": config.selectable,
        "indexes": config.indexes,
        "has_status_toggle": config.has_status_toggle,
        "recyclable": config.recyclable,
        "parent_menu": config.parent_menu,
        "permissions": config.permissions,
        "hooks": config.hooks,
    }


def _render(template_name: str, ctx: dict) -> str:
    """渲染模板并返回字符串"""
    tmpl = env.get_template(template_name)
    return tmpl.render(**ctx)


def _assert_valid_python(code: str, label: str) -> None:
    """断言代码是合法 Python"""
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


def test_enum_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("enum.py.j2", ctx)
    _assert_valid_python(code, "enum.py.j2")
    assert "class OrderStatus(LabeledStrEnum)" in code
    assert 'DRAFT = ("draft"' in code
    assert "get_transitions" in code
    assert "can_transition" in code
    print("✅ enum.py.j2 OK")


def test_model_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("model.py.j2", ctx)
    _assert_valid_python(code, "model.py.j2")
    assert "class Order(TenantModel)" in code
    assert "__tablename__" in code
    assert "__filterable__" in code
    assert "__sortable__" in code
    assert "__selectable__" in code
    assert "order_no: Mapped[str]" in code
    assert "amount: Mapped[Decimal]" in code
    assert "is_active: Mapped[bool]" in code
    assert 'ForeignKey("customers.id"' in code
    assert "customer: Mapped" in code
    assert "items: Mapped[list" in code
    assert "Index(" in code
    print("✅ model.py.j2 OK")


def test_schema_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("schema.py.j2", ctx)
    _assert_valid_python(code, "schema.py.j2")
    assert "class OrderCreate(BaseCreateSchema)" in code
    assert "class OrderUpdate(BaseUpdateSchema)" in code
    assert "class OrderResponse(TenantResponseSchema)" in code
    assert "order_no: str = Field(" in code
    assert "is_active" in code
    print("✅ schema.py.j2 OK")


def test_repository_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("repository.py.j2", ctx)
    _assert_valid_python(code, "repository.py.j2")
    assert "class OrderRepository(TenantRepository[Order])" in code
    assert "class AdminOrderRepository(BaseRepository[Order])" in code
    print("✅ repository.py.j2 OK")


def test_service_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("service.py.j2", ctx)
    _assert_valid_python(code, "service.py.j2")
    assert "class OrderService(TenantService[Order, OrderRepository])" in code
    assert "class AdminOrderService(GlobalService[Order, AdminOrderRepository])" in code
    assert "_before_create" in code
    assert "_after_create" in code
    assert "_before_delete" in code
    # Hooks not selected should not appear
    assert "_before_update" not in code
    assert "_after_update" not in code
    print("✅ service.py.j2 OK")


def test_controller_template_tenant():
    config = _build_order_config()
    ctx = _build_context(config, scope="tenant")
    code = _render("controller.py.j2", ctx)
    _assert_valid_python(code, "controller.py.j2 (tenant)")
    assert "class TenantOrderController(TenantController)" in code
    assert "permission_resource" in code
    assert "PermissionScope.TENANT" in code
    assert "register_tenant_recycle_bin_routes" in code
    assert "toggle_status" in code
    assert "get_select_options" in code
    assert "ActiveTenantAdmin" in code
    print("✅ controller.py.j2 (tenant) OK")


def test_controller_template_admin():
    config = _build_order_config()
    ctx = _build_context(config, scope="admin")
    code = _render("controller.py.j2", ctx)
    _assert_valid_python(code, "controller.py.j2 (admin)")
    assert "class AdminOrderController(GlobalController)" in code
    assert "PermissionScope.ADMIN" in code
    assert "register_admin_recycle_bin_routes" in code
    assert "ActiveAdmin" in code
    print("✅ controller.py.j2 (admin) OK")


def test_admin_scope_model():
    """scope=admin 时使用 BaseModel 而非 TenantModel"""
    config = CrudConfig(
        module="setting",
        table_name="settings",
        display_name="系统设置",
        display_name_en="Setting",
        scope=ScopeType.ADMIN,
        parent_menu="system",
        has_status_toggle=False,
        recyclable=False,
        fields=[
            FieldConfig(name="key", type=FieldType.STRING, label_zh="键", label_en="Key", required=True, max_length=100),
            FieldConfig(name="value", type=FieldType.TEXT, label_zh="值", label_en="Value"),
        ],
    )
    ctx = _build_context(config, scope="admin")
    code = _render("model.py.j2", ctx)
    _assert_valid_python(code, "model.py.j2 (admin)")
    assert "class Setting(BaseModel)" in code
    assert "TenantModel" not in code
    assert "tenant_id" not in code

    code = _render("repository.py.j2", ctx)
    _assert_valid_python(code, "repository.py.j2 (admin)")
    assert "class SettingRepository(BaseRepository[Setting])" in code
    assert "TenantRepository" not in code

    code = _render("service.py.j2", ctx)
    _assert_valid_python(code, "service.py.j2 (admin)")
    assert "class SettingService(GlobalService[Setting, SettingRepository])" in code
    assert "TenantService" not in code

    print("✅ admin scope templates OK")


if __name__ == "__main__":
    test_enum_template()
    test_model_template()
    test_schema_template()
    test_repository_template()
    test_service_template()
    test_controller_template_tenant()
    test_controller_template_admin()
    test_admin_scope_model()
    print("\n🎉 All 8 template tests passed!")
