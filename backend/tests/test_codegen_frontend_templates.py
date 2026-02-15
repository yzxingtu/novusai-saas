"""
CRUD Generator Jinja2 前端模板渲染测试

验证 7 个前端模板的渲染输出是否符合预期
"""

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
    IndexConfig,
    ListConfig,
    ListRenderPreset,
    PermissionConfig,
    RelationConfig,
    RelationType,
    ScopeType,
    SearchConfig,
    SearchFieldConfig,
    SearchOperator,
    SearchComponent,
    SelectableConfig,
    StateTransition,
)

# ---- Jinja2 环境 ----

TEMPLATE_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "app",
    "codegen",
    "templates",
    "frontend",
)


def _snake(name: str) -> str:
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
                sortable=True,
                list_render=ListRenderPreset.COPY,
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
        ],
        relations=[
            RelationConfig(
                name="customer",
                type=RelationType.BELONGS_TO,
                target_model="Customer",
                target_table="customers",
                foreign_key="customer_id",
                comment_zh="客户",
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
                    EnumOption(value="draft", label_zh="草稿", label_en="Draft", color="default"),
                    EnumOption(value="pending", label_zh="待付款", label_en="Pending", color="warning"),
                    EnumOption(value="paid", label_zh="已付款", label_en="Paid", color="success"),
                    EnumOption(value="cancelled", label_zh="已取消", label_en="Cancelled", color="error"),
                ],
            ),
        ],
        list_config=ListConfig(default_sort="-created_at"),
        form_config=FormConfig(form_type=FormType.DRAWER, drawer_width="600px"),
        selectable=SelectableConfig(
            label_field="order_no",
            value_field="id",
            search_fields=["order_no"],
        ),
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
        "search_config": config.search_config,
        "i18n_prefix": f"{scope}.{module_snake}",
    }


def _render(template_name: str, ctx: dict) -> str:
    tmpl = env.get_template(template_name)
    return tmpl.render(**ctx)


# ---- Tests ----


def test_api_ts_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("api.ts.j2", ctx)

    assert "export interface OrderItem {" in code
    assert "export interface OrderCreateRequest {" in code
    assert "export interface OrderUpdateRequest {" in code
    assert "getOrderListApi" in code
    assert "getOrderDetailApi" in code
    assert "createOrderApi" in code
    assert "updateOrderApi" in code
    assert "deleteOrderApi" in code
    assert "toggleOrderStatusApi" in code
    assert "getOrderSelectApi" in code
    assert "requestClient" in code
    assert "/tenant/business/orders" in code
    assert "order_no: string;" in code
    assert "amount: number;" in code
    assert "is_urgent: boolean;" in code
    assert "customer_id: number" in code
    print("✅ api.ts.j2 OK")


def test_data_ts_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("data.ts.j2", ctx)

    assert "useColumns" in code
    assert "useGridFormSchema" in code
    assert "useFormSchema" in code
    assert "getOrderStatusOptions" in code
    assert "getOrderStatusText" in code
    assert "getOrderStatusColor" in code
    assert "searchInput" in code
    assert "statusSelect" in code
    assert "inputField" in code
    assert "numberField" in code
    assert "textareaField" in code
    assert "switchField" in code
    assert "dateField" in code
    assert "CellOperation" in code
    assert "is_active" in code
    print("✅ data.ts.j2 OK")


def test_index_vue_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("index.vue.j2", ctx)

    assert "<script lang=\"ts\" setup>" in code
    assert "useCrudPage" in code
    assert "getOrderListApi" in code
    assert "deleteOrderApi" in code
    assert "toggleOrderStatusApi" in code
    assert "OrderForm" in code
    assert "recycleBin: true" in code
    assert "getOrderStatusColor" in code
    assert "getOrderStatusText" in code
    assert "#status_cell" in code
    assert "#is_active_cell" in code
    assert "<Switch" in code
    assert "<Tag" in code
    print("✅ index.vue.j2 OK")


def test_form_vue_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("form.vue.j2", ctx)

    assert "<script lang=\"ts\" setup>" in code
    assert "useCrudDrawer" in code
    assert "useVbenForm" in code
    assert "useFormSchema" in code
    assert "OrderItem" in code
    assert "/tenant/business/orders" in code
    assert "'order_no'" in code
    assert "'amount'" in code
    assert "'status'" in code
    assert "'remark'" in code
    assert "'is_active'" in code
    assert "'customer_id'" in code
    assert "openNew" in code
    assert "openEdit" in code
    assert 'class="w-[600px]"' in code
    print("✅ form.vue.j2 OK")


def test_admin_scope_api():
    """scope=admin 不应包含 tenant_id"""
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
    code = _render("api.ts.j2", ctx)

    assert "tenant_id" not in code
    assert "/admin/system/settings" in code
    assert "export interface SettingItem {" in code
    print("✅ api.ts.j2 (admin) OK")


def test_index_card_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("index_card.vue.j2", ctx)

    assert "<script lang=\"ts\" setup>" in code
    assert "getOrderListApi" in code
    assert "OrderForm" in code
    assert "<Card hoverable" in code
    assert "<Pagination" in code
    assert "page[number]" in code
    assert "page[size]" in code
    print("✅ index_card.vue.j2 OK")


def test_index_kanban_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("index_kanban.vue.j2", ctx)

    assert "<script lang=\"ts\" setup>" in code
    assert "getOrderListApi" in code
    assert "groupedItems" in code
    assert "columns" in code
    assert "draft" in code
    assert "pending" in code
    assert "paid" in code
    assert "<Badge" in code
    print("✅ index_kanban.vue.j2 OK")


def test_index_split_template():
    config = _build_order_config()
    ctx = _build_context(config)
    code = _render("index_split.vue.j2", ctx)

    assert "<script lang=\"ts\" setup>" in code
    assert "useCrudPage" in code
    assert "getOrderDetailApi" in code
    assert "selectedItem" in code
    assert "w-3/5" in code
    assert "w-2/5" in code
    assert "selectToView" in code
    print("✅ index_split.vue.j2 OK")


if __name__ == "__main__":
    test_api_ts_template()
    test_data_ts_template()
    test_index_vue_template()
    test_form_vue_template()
    test_admin_scope_api()
    test_index_card_template()
    test_index_kanban_template()
    test_index_split_template()
    print("\n🎉 All 8 frontend template tests passed!")
