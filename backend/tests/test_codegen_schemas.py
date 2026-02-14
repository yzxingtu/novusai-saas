"""
CRUD Generator Schema 序列化/反序列化测试
"""

import json

from app.codegen.schemas import (
    AnimationConfig,
    AuditConfig,
    BatchAction,
    CrudConfig,
    CustomSlotConfig,
    EnumDefinition,
    EnumOption,
    FieldConfig,
    FieldType,
    FormConfig,
    FormDependency,
    FormGroup,
    FormType,
    GitConfig,
    ImportExportConfig,
    IndexConfig,
    InlineEditConfig,
    LayoutConfig,
    LayoutVariant,
    ListConfig,
    ListRenderPreset,
    LogicFlow,
    LogicNode,
    LogicNodeType,
    NLQueryConfig,
    ObservabilityConfig,
    PermissionAction,
    PermissionConfig,
    RelationConfig,
    RelationType,
    ScopeType,
    SearchComponent,
    SearchConfig,
    SearchFieldConfig,
    SearchOperator,
    SelectableConfig,
    StateTransition,
    StyleConfig,
    TestScaffoldConfig,
    TreeSelectConfig,
    UploadFieldConfig,
    ValidationRule,
)


def build_order_config() -> CrudConfig:
    """构建一个完整的订单管理模块配置用于测试"""
    return CrudConfig(
        module="order",
        table_name="orders",
        display_name="订单",
        display_name_en="Order",
        scope=ScopeType.TENANT,
        parent_menu="business",
        description="订单管理模块",
        soft_delete=True,
        drag_sort=False,
        has_status_toggle=False,
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
                search_op=SearchOperator.ILIKE,
                list_render=ListRenderPreset.COPY,
                form_rules=[
                    ValidationRule(
                        type="regex",
                        value=r"^[A-Z]{2}-\d{6}$",
                        message_zh="格式: XX-000000",
                        message_en="Format: XX-000000",
                    ),
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
                list_render=ListRenderPreset.MONEY,
                list_align="right",
                sortable=True,
                form_rules=[
                    ValidationRule(type="min", value=0, message_zh="金额不能为负"),
                ],
            ),
            FieldConfig(
                name="status",
                type=FieldType.ENUM,
                label_zh="状态",
                label_en="Status",
                enum_ref="OrderStatus",
                list_render=ListRenderPreset.TAG,
                searchable=True,
                search_op=SearchOperator.EQ,
            ),
            FieldConfig(
                name="remark",
                type=FieldType.TEXT,
                label_zh="备注",
                label_en="Remark",
                in_list=False,
                form_component="Textarea",
            ),
            FieldConfig(
                name="attachment",
                type=FieldType.FILE,
                label_zh="附件",
                label_en="Attachment",
                in_list=False,
                upload=UploadFieldConfig(
                    upload_type="file",
                    accept=".pdf,.doc,.docx",
                    max_size_mb=20,
                    max_count=5,
                ),
            ),
            FieldConfig(
                name="weight",
                type=FieldType.FLOAT,
                label_zh="重量",
                label_en="Weight",
                in_list=False,
                form_depends_on=FormDependency(
                    field="order_type",
                    condition="eq",
                    value="physical",
                ),
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
            ),
            RelationConfig(
                name="items",
                type=RelationType.HAS_MANY,
                target_model="OrderItem",
                target_table="order_items",
                cascade_delete=True,
            ),
        ],
        search_config=SearchConfig(
            fields=[
                SearchFieldConfig(
                    field="order_no",
                    operator=SearchOperator.ILIKE,
                    component=SearchComponent.INPUT,
                    placeholder_zh="请输入订单编号",
                    placeholder_en="Enter order no.",
                ),
                SearchFieldConfig(
                    field="status",
                    operator=SearchOperator.EQ,
                    component=SearchComponent.SELECT,
                    options_enum="OrderStatus",
                ),
                SearchFieldConfig(
                    field="created_at",
                    operator=SearchOperator.BETWEEN,
                    component=SearchComponent.RANGE_PICKER,
                ),
            ],
            collapsed=True,
            max_visible=3,
        ),
        enums=[
            EnumDefinition(
                name="OrderStatus",
                description="订单状态",
                values=[
                    EnumOption(value="draft", label_zh="草稿", label_en="Draft", color="default"),
                    EnumOption(value="pending", label_zh="待付款", label_en="Pending", color="warning"),
                    EnumOption(value="paid", label_zh="已付款", label_en="Paid", color="processing"),
                    EnumOption(value="shipped", label_zh="已发货", label_en="Shipped", color="processing"),
                    EnumOption(value="completed", label_zh="已完成", label_en="Completed", color="success"),
                    EnumOption(value="cancelled", label_zh="已取消", label_en="Cancelled", color="error"),
                ],
                transitions=[
                    StateTransition(
                        from_state="draft", to_state="pending",
                        action="submit", label_zh="提交", label_en="Submit",
                    ),
                    StateTransition(
                        from_state="pending", to_state="paid",
                        action="pay", label_zh="付款", label_en="Pay",
                    ),
                    StateTransition(
                        from_state="paid", to_state="shipped",
                        action="ship", label_zh="发货", label_en="Ship",
                    ),
                    StateTransition(
                        from_state="shipped", to_state="completed",
                        action="complete", label_zh="完成", label_en="Complete",
                    ),
                    StateTransition(
                        from_state="draft", to_state="cancelled",
                        action="cancel", label_zh="取消", label_en="Cancel",
                        confirm=True,
                    ),
                    StateTransition(
                        from_state="pending", to_state="cancelled",
                        action="cancel", label_zh="取消", label_en="Cancel",
                        confirm=True,
                    ),
                ],
            ),
        ],
        list_config=ListConfig(
            show_checkbox=True,
            default_sort="-created_at",
            stripe=True,
        ),
        form_config=FormConfig(
            drawer_width="600px",
            form_type=FormType.DRAWER,
            groups=[
                FormGroup(
                    title_zh="基本信息",
                    title_en="Basic Info",
                    fields=["order_no", "customer_name", "amount", "status"],
                ),
                FormGroup(
                    title_zh="详细信息",
                    title_en="Details",
                    fields=["remark", "attachment", "weight"],
                    collapsible=True,
                ),
            ],
        ),
        operations=["edit", "delete"],
        selectable=SelectableConfig(
            label_field="order_no",
            value_field="id",
            search_fields=["order_no", "customer_name"],
        ),
        indexes=[
            IndexConfig(fields=["tenant_id", "status"]),
            IndexConfig(fields=["tenant_id", "order_no"], unique=True),
        ],
        import_export=ImportExportConfig(
            enable_export=True,
            enable_import=True,
            batch_delete=True,
            batch_custom=[
                BatchAction(
                    code="batch_ship",
                    label_zh="批量发货",
                    label_en="Batch Ship",
                    icon="lucide:truck",
                    confirm=True,
                    permission="order:ship",
                ),
            ],
        ),
        permissions=PermissionConfig(
            actions=["read", "create", "update", "delete"],
            extra_actions=[
                PermissionAction(code="ship", label_zh="发货", label_en="Ship"),
                PermissionAction(code="export", label_zh="导出", label_en="Export"),
            ],
            menu_icon="lucide:shopping-cart",
            menu_sort_order=10,
        ),
        hooks=["before_create", "after_create", "before_delete"],
        custom_slots=[
            CustomSlotConfig(
                field="amount",
                slot_type="column",
                template='<span :class="row.amount > 1000 ? \'text-red-500\' : \'text-green-500\'">¥{{ row.amount }}</span>',
                description="金额大于1000红色，否则绿色",
            ),
        ],
        layout=LayoutConfig(variant=LayoutVariant.STANDARD),
        style=StyleConfig(bordered=True, header_sticky=True),
        animation=AnimationConfig(skeleton_loading=True),
        git=GitConfig(auto_branch=True, auto_commit=True),
        audit=AuditConfig(
            enable=True,
            sensitive_fields=["amount"],
        ),
        test=TestScaffoldConfig(generate_unit_tests=True, generate_api_tests=True),
        inline_edit=InlineEditConfig(
            enable=True,
            editable_fields=["status", "remark"],
            save_mode="cell",
        ),
        logic_flows=[
            LogicFlow(
                hook="before_create",
                entry_node_id="n1",
                description="创建前自动生成订单编号",
                nodes=[
                    LogicNode(
                        id="n1",
                        type=LogicNodeType.ASSIGN,
                        label="生成订单编号",
                        config={"field": "order_no", "expression": "generate_order_no()"},
                        next_nodes=["n2"],
                    ),
                    LogicNode(
                        id="n2",
                        type=LogicNodeType.VALIDATE,
                        label="校验金额",
                        config={"field": "amount", "rule": "gt", "value": 0},
                    ),
                ],
            ),
        ],
    )


def test_full_serialization():
    """测试完整配置的 JSON 序列化/反序列化"""
    config = build_order_config()

    # 序列化
    json_str = config.model_dump_json(indent=2)
    json_dict = json.loads(json_str)

    # 基本字段
    assert json_dict["module"] == "order"
    assert json_dict["table_name"] == "orders"
    assert json_dict["scope"] == "tenant"
    assert len(json_dict["fields"]) == 7
    assert len(json_dict["enums"]) == 1
    assert len(json_dict["relations"]) == 2

    # 枚举
    status_enum = json_dict["enums"][0]
    assert status_enum["name"] == "OrderStatus"
    assert len(status_enum["values"]) == 6
    assert len(status_enum["transitions"]) == 6

    # 搜索
    assert len(json_dict["search_config"]["fields"]) == 3

    # 高级配置
    assert json_dict["inline_edit"]["enable"] is True
    assert len(json_dict["logic_flows"]) == 1
    assert len(json_dict["logic_flows"][0]["nodes"]) == 2
    assert json_dict["git"]["auto_branch"] is True

    # 反序列化
    restored = CrudConfig.model_validate_json(json_str)
    assert restored.module == "order"
    assert restored.fields[0].name == "order_no"
    assert restored.fields[0].list_render == ListRenderPreset.COPY
    assert restored.enums[0].transitions[0].from_state == "draft"
    assert restored.relations[0].type == RelationType.BELONGS_TO
    assert restored.logic_flows[0].nodes[0].type == LogicNodeType.ASSIGN

    # 再次序列化确保一致
    json_str2 = restored.model_dump_json(indent=2)
    assert json.loads(json_str) == json.loads(json_str2)

    print(f"✅ Full serialization test passed ({len(json_str)} bytes)")


def test_minimal_config():
    """测试最小配置 (只有必填字段)"""
    config = CrudConfig(
        module="tag",
        table_name="tags",
        display_name="标签",
        display_name_en="Tag",
        parent_menu="system",
        fields=[
            FieldConfig(
                name="name",
                type=FieldType.STRING,
                label_zh="名称",
                label_en="Name",
                required=True,
            ),
        ],
    )

    json_str = config.model_dump_json()
    restored = CrudConfig.model_validate_json(json_str)

    assert restored.module == "tag"
    assert restored.scope == ScopeType.TENANT  # default
    assert restored.soft_delete is True  # default
    assert restored.list_config.stripe is True  # default
    assert restored.form_config.drawer_width == "600px"  # default
    assert restored.animation.skeleton_loading is True  # default
    assert restored.git.auto_branch is False  # default
    assert len(restored.fields) == 1
    assert len(restored.relations) == 0  # default empty
    assert len(restored.enums) == 0  # default empty

    print("✅ Minimal config test passed")


def test_dict_roundtrip():
    """测试 dict 序列化/反序列化"""
    config = build_order_config()

    # model_dump → model_validate
    d = config.model_dump()
    restored = CrudConfig.model_validate(d)
    assert restored.module == config.module
    assert len(restored.fields) == len(config.fields)

    # model_dump(mode="json") for JSON-safe dict
    json_d = config.model_dump(mode="json")
    assert isinstance(json_d["scope"], str)
    assert json_d["scope"] == "tenant"

    print("✅ Dict roundtrip test passed")


def test_all_enum_values():
    """测试所有枚举值可被正确序列化"""
    from app.codegen.schemas import (
        FormComponent,
        SearchComponent as SC,
        SearchOperator as SO,
    )

    for ft in FieldType:
        f = FieldConfig(name="test", type=ft, label_zh="测试", label_en="Test")
        d = f.model_dump(mode="json")
        assert d["type"] == ft.value

    for rt in RelationType:
        r = RelationConfig(
            name="test", type=rt, target_model="X", target_table="x"
        )
        d = r.model_dump(mode="json")
        assert d["type"] == rt.value

    for lv in LayoutVariant:
        lc = LayoutConfig(variant=lv)
        d = lc.model_dump(mode="json")
        assert d["variant"] == lv.value

    for lrp in ListRenderPreset:
        f = FieldConfig(
            name="test", type=FieldType.STRING,
            label_zh="测试", label_en="Test",
            list_render=lrp,
        )
        d = f.model_dump(mode="json")
        assert d["list_render"] == lrp.value

    for nt in LogicNodeType:
        n = LogicNode(id="x", type=nt)
        d = n.model_dump(mode="json")
        assert d["type"] == nt.value

    print(f"✅ All enum values serialization passed "
          f"(FieldType={len(FieldType)}, RelationType={len(RelationType)}, "
          f"LayoutVariant={len(LayoutVariant)}, ListRenderPreset={len(ListRenderPreset)}, "
          f"LogicNodeType={len(LogicNodeType)})")


if __name__ == "__main__":
    test_full_serialization()
    test_minimal_config()
    test_dict_roundtrip()
    test_all_enum_values()
    print("\n🎉 All tests passed!")
