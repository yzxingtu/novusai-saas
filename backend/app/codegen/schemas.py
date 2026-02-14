"""
CRUD 代码生成器 — Pydantic Schema 全量定义

定义代码生成器所需的所有配置模型，覆盖：
- 基本信息、字段定义、关联关系、搜索配置
- 枚举 & 状态机、列表配置、表单配置
- 列渲染预设、条件字段、文件上传、下拉选项
- 校验规则、复合索引、权限、导入导出
- 自定义 Slot、布局变体、样式、动画
- AI 翻译、Git 集成、审计、测试、可观测性
- 可视化逻辑编排 (LogicFlow)

参考设计文档 §1-§25, §26-§32, §33-§34
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "FieldType",
    "RelationType",
    "LayoutVariant",
    "ListRenderPreset",
    "ScopeType",
    "FormType",
    "SearchOperator",
    "SearchComponent",
    "FormComponent",
    "HookType",
    "LogicNodeType",
    "EnumOption",
    "StateTransition",
    "EnumDefinition",
    "ValidationRule",
    "FormDependency",
    "UploadFieldConfig",
    "FieldConfig",
    "RelationConfig",
    "SearchFieldConfig",
    "SearchConfig",
    "ListConfig",
    "FormGroup",
    "FormConfig",
    "TreeSelectConfig",
    "SelectableConfig",
    "IndexConfig",
    "PermissionAction",
    "PermissionConfig",
    "BatchAction",
    "ImportExportConfig",
    "CustomSlotConfig",
    "LayoutConfig",
    "StyleConfig",
    "AnimationConfig",
    "GitConfig",
    "AuditConfig",
    "TestScaffoldConfig",
    "InlineEditConfig",
    "ObservabilityConfig",
    "NLQueryConfig",
    "LogicNode",
    "LogicFlow",
    "CrudConfig",
    "EntityRelation",
    "BatchCrudProject",
]


# ============================================================
# 基础枚举
# ============================================================


class FieldType(str, Enum):
    """字段数据类型"""

    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    JSON = "json"
    ENUM = "enum"
    FILE = "file"


class RelationType(str, Enum):
    """关联关系类型"""

    BELONGS_TO = "belongs_to"
    HAS_MANY = "has_many"
    MANY_TO_MANY = "many_to_many"
    SELF_REF_TREE = "self_ref_tree"


class LayoutVariant(str, Enum):
    """页面布局变体"""

    STANDARD = "standard"
    CARD_LIST = "card_list"
    MASTER_DETAIL = "master_detail"
    TREE_TABLE = "tree_table"
    KANBAN = "kanban"
    TIMELINE = "timeline"


class ListRenderPreset(str, Enum):
    """列渲染预设类型 (§15)"""

    TAG = "tag"
    SWITCH = "switch"
    MONEY = "money"
    PERCENT = "percent"
    RELATIVE_TIME = "relative_time"
    DATETIME = "datetime"
    DATE = "date"
    AVATAR = "avatar"
    IMAGE = "image"
    LINK = "link"
    COPY = "copy"
    PROGRESS = "progress"
    ELLIPSIS = "ellipsis"
    BADGE = "badge"
    ICON = "icon"
    COLOR = "color"


class ScopeType(str, Enum):
    """生成范围"""

    ADMIN = "admin"
    TENANT = "tenant"
    BOTH = "both"


class FormType(str, Enum):
    """表单容器类型"""

    DRAWER = "drawer"
    MODAL = "modal"


class SearchOperator(str, Enum):
    """搜索操作符"""

    ILIKE = "ilike"
    EQ = "eq"
    IN = "in"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"


class SearchComponent(str, Enum):
    """搜索组件类型"""

    INPUT = "Input"
    SELECT = "Select"
    DATE_PICKER = "DatePicker"
    RANGE_PICKER = "RangePicker"
    INPUT_NUMBER = "InputNumber"
    API_SELECT = "ApiSelect"
    TREE_SELECT = "TreeSelect"


class FormComponent(str, Enum):
    """表单组件类型"""

    INPUT = "Input"
    INPUT_NUMBER = "InputNumber"
    TEXTAREA = "Textarea"
    SELECT = "Select"
    SWITCH = "Switch"
    DATE_PICKER = "DatePicker"
    RANGE_PICKER = "RangePicker"
    RADIO_GROUP = "RadioGroup"
    CHECKBOX_GROUP = "CheckboxGroup"
    UPLOAD = "Upload"
    API_SELECT = "ApiSelect"
    API_TREE_SELECT = "ApiTreeSelect"
    CASCADER = "Cascader"
    RATE = "Rate"
    SLIDER = "Slider"
    COLOR_PICKER = "ColorPicker"
    JSON_EDITOR = "JsonEditor"
    RICH_TEXT = "RichText"


class HookType(str, Enum):
    """Service 钩子类型"""

    BEFORE_CREATE = "before_create"
    AFTER_CREATE = "after_create"
    BEFORE_UPDATE = "before_update"
    AFTER_UPDATE = "after_update"
    BEFORE_DELETE = "before_delete"
    AFTER_DELETE = "after_delete"
    BEFORE_LIST = "before_list"
    AFTER_LIST = "after_list"


class LogicNodeType(str, Enum):  # Phase 7 reserved
    """逻辑编排节点类型 (§32.6)"""

    VALIDATE = "validate"
    TRANSFORM = "transform"
    CONDITION = "condition"
    QUERY = "query"
    NOTIFY = "notify"
    ASSIGN = "assign"
    LOOP = "loop"
    ERROR = "error"


# ============================================================
# 原子配置块
# ============================================================


class EnumOption(BaseModel):
    """枚举选项"""

    value: str = Field(..., description="枚举值 (snake_case)")
    label_zh: str = Field(..., description="中文标签")
    label_en: str = Field(..., description="英文标签")
    color: str | None = Field(None, description="Tag 颜色 (success/warning/error/processing/default)")
    icon: str | None = Field(None, description="图标 (lucide:xxx)")


class StateTransition(BaseModel):
    """状态流转定义 (§14)"""

    from_state: str = Field(..., description="起始状态值")
    to_state: str = Field(..., description="目标状态值")
    action: str = Field(..., description="动作标识 (snake_case)")
    label_zh: str = Field(..., description="动作中文标签")
    label_en: str = Field(..., description="动作英文标签")
    confirm: bool = Field(True, description="是否需要确认弹窗")
    permission: str | None = Field(None, description="所需权限码")


class EnumDefinition(BaseModel):
    """枚举定义 (§14)"""

    name: str = Field(..., description="枚举类名 PascalCase (如 OrderStatus)")
    description: str = Field("", description="枚举描述")
    values: list[EnumOption] = Field(..., description="枚举选项列表")
    transitions: list[StateTransition] | None = Field(
        None, description="状态流转 (仅状态机枚举)"
    )


class ValidationRule(BaseModel):
    """自定义校验规则 (§23)"""

    type: str = Field(
        ...,
        description="规则类型: required|regex|min|max|minLength|maxLength|email|url|phone|custom",
    )
    value: Any | None = Field(None, description="规则值 (如 regex 表达式、min 数值)")
    message_zh: str | None = Field(None, description="中文错误提示")
    message_en: str | None = Field(None, description="英文错误提示")


class FormDependency(BaseModel):
    """表单字段条件显示 (§20)"""

    field: str = Field(..., description="依赖的字段名")
    condition: str = Field(
        ..., description="条件: eq|neq|in|notIn|truthy|falsy"
    )
    value: Any | None = Field(None, description="条件值 (condition=eq/neq)")
    values: list[Any] | None = Field(None, description="条件值列表 (condition=in/notIn)")


class UploadFieldConfig(BaseModel):
    """文件上传字段配置 (§19)"""

    upload_type: str = Field("file", description="上传类型: file|image|avatar")
    accept: str = Field("*", description="接受的文件类型 (如 .jpg,.png 或 image/*)")
    max_size_mb: int = Field(10, description="最大文件大小 (MB)")
    max_count: int = Field(1, description="最大文件数量 (>1 时为多文件)")
    storage: str = Field("attachment", description="存储方式: attachment")


# ============================================================
# 字段配置
# ============================================================


class FieldConfig(BaseModel):
    """单个字段配置 (§3.2)"""

    # ---- 基础 ----
    name: str = Field(..., description="字段名 snake_case")
    type: FieldType = Field(..., description="字段数据类型")
    label_zh: str = Field(..., description="中文标签")
    label_en: str = Field(..., description="英文标签")

    # ---- 数据库约束 ----
    required: bool = Field(False, description="是否必填")
    nullable: bool = Field(True, description="是否允许 NULL")
    unique: bool = Field(False, description="是否唯一约束")
    max_length: int | None = Field(None, description="最大长度 (type=string)")
    default: Any | None = Field(None, description="默认值")
    index: bool = Field(False, description="是否单独建索引")

    # ---- 枚举 ----
    enum_ref: str | None = Field(None, description="引用 enums[] 中的枚举名")
    enum_values: list[EnumOption] | None = Field(None, description="内联枚举 (简单场景)")

    # ---- 关联字段 ----
    relation_ref: str | None = Field(None, description="引用 relations[] 中的关联名")

    # ---- JSON:API 查询 ----
    filterable: bool = Field(True, description="是否可过滤")
    sortable: bool = Field(False, description="是否可排序")

    # ---- 搜索 ----
    searchable: bool = Field(False, description="是否出现在搜索栏")
    search_op: SearchOperator = Field(SearchOperator.ILIKE, description="搜索操作符")

    # ---- 列表 ----
    in_list: bool = Field(True, description="是否显示在列表中")
    list_width: int | None = Field(None, description="列宽度 (px)")
    list_align: str = Field("left", description="列对齐: left|center|right")
    list_render: ListRenderPreset | None = Field(None, description="列渲染预设")
    list_slot: str | None = Field(None, description="自定义 slot 名 (与 list_render 互斥)")
    list_fixed: str | None = Field(None, description="列固定: left|right")
    list_sortable: bool = Field(False, description="列头排序")

    # ---- 表单 ----
    in_form: bool = Field(True, description="是否显示在表单中")
    form_component: FormComponent = Field(FormComponent.INPUT, description="表单组件")
    form_group: str | None = Field(None, description="分组标题 (Divider)")
    form_placeholder: str | None = Field(None, description="表单占位文本")
    form_rules: list[ValidationRule] | None = Field(None, description="自定义校验规则")
    form_depends_on: FormDependency | None = Field(None, description="条件显示")
    form_col_span: int | None = Field(None, description="表单列跨度 (栅格)")
    form_help: str | None = Field(None, description="字段帮助文本")

    # ---- 文件上传 ----
    upload: UploadFieldConfig | None = Field(None, description="type=file 时的上传配置")


# ============================================================
# 关联关系
# ============================================================


class RelationConfig(BaseModel):
    """关联关系配置 (§13)"""

    name: str = Field(..., description="关联名 snake_case (如 customer)")
    type: RelationType = Field(..., description="关联类型")
    target_model: str = Field(..., description="目标模型 PascalCase (如 Customer)")
    target_table: str = Field(..., description="目标表名 snake_case (如 customers)")
    foreign_key: str | None = Field(None, description="外键字段名 (belongs_to 时)")
    pivot_table: str | None = Field(None, description="中间表名 (many_to_many 时)")
    cascade_delete: bool = Field(False, description="级联删除")
    label_field: str = Field("name", description="关联模型显示字段 (下拉框标签)")
    nullable: bool = Field(True, description="外键是否可为空")
    comment_zh: str = Field("", description="关联中文说明")
    comment_en: str = Field("", description="关联英文说明")


# ============================================================
# 搜索配置
# ============================================================


class SearchFieldConfig(BaseModel):
    """搜索字段配置 (§13.2)"""

    field: str = Field(..., description="字段名")
    operator: SearchOperator = Field(SearchOperator.ILIKE, description="操作符")
    component: SearchComponent = Field(SearchComponent.INPUT, description="搜索组件")
    placeholder_zh: str | None = Field(None, description="中文占位符")
    placeholder_en: str | None = Field(None, description="英文占位符")
    api: str | None = Field(None, description="远程数据 API (ApiSelect 时)")
    options_enum: str | None = Field(None, description="枚举引用 (Select 时)")
    default_value: Any | None = Field(None, description="默认值")
    col_span: int = Field(6, description="栅格宽度 (24栅格)")


class SearchConfig(BaseModel):
    """搜索栏配置 (§13.2)"""

    fields: list[SearchFieldConfig] = Field(default_factory=list, description="搜索字段列表")
    collapsed: bool = Field(True, description="默认折叠")
    max_visible: int = Field(3, description="折叠时可见字段数")


# ============================================================
# 列表 & 表单配置
# ============================================================


class ListConfig(BaseModel):
    """列表页配置 (§3.3)"""

    show_checkbox: bool = Field(True, description="显示复选框")
    show_index: bool = Field(False, description="显示行号")
    default_sort: str = Field("-created_at", description="默认排序")
    row_height: int = Field(64, description="行高 (px)")
    stripe: bool = Field(True, description="斑马纹")
    pager: bool = Field(True, description="分页")
    toolbar_export: bool = Field(True, description="导出按钮")
    toolbar_search: bool = Field(True, description="搜索栏")


class FormGroup(BaseModel):
    """表单分组 (§3.4)"""

    title_zh: str = Field(..., description="分组标题 (中文)")
    title_en: str = Field(..., description="分组标题 (英文)")
    fields: list[str] = Field(..., description="分组包含的字段名列表")
    collapsible: bool = Field(False, description="是否可折叠")
    default_collapsed: bool = Field(False, description="默认折叠")


class FormConfig(BaseModel):
    """表单配置 (§3.4)"""

    drawer_width: str = Field("600px", description="抽屉宽度")
    form_type: FormType = Field(FormType.DRAWER, description="容器类型")
    groups: list[FormGroup] | None = Field(None, description="表单分组")
    columns: int = Field(1, description="表单列数 (1 或 2)")
    label_width: int = Field(120, description="标签宽度 (px)")


# ============================================================
# 下拉选项 API
# ============================================================


class TreeSelectConfig(BaseModel):
    """树形下拉配置 (§18)"""

    parent_field: str = Field("parent_id", description="父级字段")
    children_field: str = Field("children", description="子级字段")
    order_by: str = Field("sort_order", description="排序字段")


class SelectableConfig(BaseModel):
    """下拉选项 API 配置 (§18)"""

    label_field: str = Field("name", description="显示字段")
    value_field: str = Field("id", description="值字段")
    search_fields: list[str] = Field(default_factory=list, description="搜索字段")
    extra_fields: list[str] = Field(default_factory=list, description="额外返回字段")
    tree: TreeSelectConfig | None = Field(None, description="树形下拉配置")


# ============================================================
# 复合索引
# ============================================================


class IndexConfig(BaseModel):
    """复合索引定义 (§24)"""

    name: str | None = Field(None, description="索引名 (None 时自动生成)")
    fields: list[str] = Field(..., description="字段列表")
    unique: bool = Field(False, description="是否唯一索引")


# ============================================================
# 权限配置
# ============================================================


class PermissionAction(BaseModel):
    """额外权限操作 (§22)"""

    code: str = Field(..., description="操作码 (如 publish/export)")
    label_zh: str = Field(..., description="中文标签")
    label_en: str = Field(..., description="英文标签")


class PermissionConfig(BaseModel):
    """RBAC 权限配置 (§22)"""

    resource_code: str | None = Field(None, description="权限资源码 (默认从 module 推导)")
    actions: list[str] = Field(
        default_factory=lambda: ["read", "create", "update", "delete"],
        description="标准权限操作",
    )
    extra_actions: list[PermissionAction] | None = Field(None, description="额外权限操作")
    menu_icon: str = Field("lucide:file-text", description="菜单图标")
    menu_sort_order: int = Field(10, description="菜单排序")


# ============================================================
# 导入导出
# ============================================================


class BatchAction(BaseModel):
    """自定义批量操作 (§21)"""

    code: str = Field(..., description="操作代码")
    label_zh: str = Field(..., description="中文标签")
    label_en: str = Field(..., description="英文标签")
    icon: str | None = Field(None, description="图标")
    confirm: bool = Field(True, description="是否需要确认")
    permission: str | None = Field(None, description="所需权限码")


class ImportExportConfig(BaseModel):
    """导入导出配置 (§21)"""

    enable_export: bool = Field(True, description="启用导出")
    enable_import: bool = Field(False, description="启用导入")
    export_fields: list[str] | None = Field(None, description="导出字段 (None=全部)")
    import_fields: list[str] | None = Field(None, description="导入字段")
    import_template: bool = Field(True, description="生成导入模板下载")
    batch_delete: bool = Field(True, description="批量删除")
    batch_status: bool = Field(False, description="批量启用/禁用")
    batch_custom: list[BatchAction] | None = Field(None, description="自定义批量操作")


# ============================================================
# 自定义 Slot (§27)
# ============================================================


class CustomSlotConfig(BaseModel):
    """自定义列/字段渲染 Slot (§27)"""

    field: str = Field(..., description="关联字段名")
    slot_type: str = Field("column", description="slot 类型: column|form")
    template: str = Field("", description="Vue template 代码片段")
    description: str = Field("", description="功能描述 (供 AI 生成参考)")
    ai_generated: bool = Field(False, description="是否由 AI 生成")


# ============================================================
# 布局 & 样式
# ============================================================


class LayoutConfig(BaseModel):
    """页面布局配置 (§32.3)"""

    variant: LayoutVariant = Field(LayoutVariant.STANDARD, description="布局变体")
    card_fields: list[str] | None = Field(
        None, description="卡片显示字段 (card_list 时)"
    )
    card_cover_field: str | None = Field(None, description="卡片封面字段")
    card_columns: int = Field(3, description="卡片列数")
    detail_position: str = Field("right", description="详情位置: right|bottom (master_detail 时)")
    detail_width: str = Field("40%", description="详情宽度")
    kanban_group_field: str | None = Field(None, description="看板分组字段 (kanban 时)")
    timeline_date_field: str | None = Field(None, description="时间线日期字段 (timeline 时)")


class StyleConfig(BaseModel):
    """样式配置 (§32)"""

    primary_color: str | None = Field(None, description="主色调 (覆盖全局)")
    compact: bool = Field(False, description="紧凑模式")
    bordered: bool = Field(True, description="表格边框")
    rounded: bool = Field(True, description="圆角")
    header_sticky: bool = Field(True, description="表头固定")
    custom_css: str | None = Field(None, description="自定义 CSS")


# ============================================================
# 动画配置 (§32.8)
# ============================================================


class AnimationConfig(BaseModel):
    """生成页面的动画配置"""

    row_enter: bool = Field(True, description="行进入动画 (stagger fade-in)")
    drawer_transition: bool = Field(True, description="Drawer/Modal 进出动画")
    status_transition: bool = Field(True, description="状态切换颜色渐变")
    skeleton_loading: bool = Field(True, description="骨架屏 loading")


# ============================================================
# Git 集成 (§32.9)
# ============================================================


class GitConfig(BaseModel):
    """Git 集成配置"""

    auto_branch: bool = Field(False, description="自动创建分支 feat/crud-{module}")
    auto_commit: bool = Field(False, description="自动 commit")
    commit_message_template: str = Field(
        "feat({module}): scaffold CRUD for {display_name}",
        description="Commit 消息模板",
    )


# ============================================================
# 审计 & 测试 & 可观测性
# ============================================================


class AuditConfig(BaseModel):
    """审计日志配置"""

    enable: bool = Field(True, description="启用操作审计")
    log_fields: list[str] | None = Field(
        None, description="记录变更的字段 (None=全部)"
    )
    sensitive_fields: list[str] = Field(
        default_factory=list, description="敏感字段 (日志中脱敏)"
    )


class TestScaffoldConfig(BaseModel):
    """测试脚手架配置"""

    generate_unit_tests: bool = Field(True, description="生成单元测试")
    generate_api_tests: bool = Field(True, description="生成 API 测试")
    test_data_count: int = Field(5, description="测试数据条数")
    custom_fixtures: list[str] = Field(
        default_factory=list, description="自定义 fixture 名称"
    )


class InlineEditConfig(BaseModel):
    """行内编辑配置 (§32.5)"""

    enable: bool = Field(False, description="启用行内编辑")
    editable_fields: list[str] = Field(
        default_factory=list, description="可行内编辑的字段列表"
    )
    save_mode: str = Field("cell", description="保存模式: cell|row|batch")
    debounce_ms: int = Field(300, description="保存防抖时间 (ms)")


class ObservabilityConfig(BaseModel):
    """可观测性配置"""

    enable_metrics: bool = Field(False, description="启用 API 指标收集")
    enable_tracing: bool = Field(False, description="启用链路追踪")
    slow_query_threshold_ms: int = Field(1000, description="慢查询阈值 (ms)")
    custom_tags: dict[str, str] = Field(
        default_factory=dict, description="自定义标签 (k:v)"
    )


class NLQueryConfig(BaseModel):
    """自然语言数据查询配置 (§33.3)"""

    enable: bool = Field(False, description="启用自然语言查询")
    query_fields: list[str] = Field(
        default_factory=list, description="可查询字段"
    )
    example_queries_zh: list[str] = Field(
        default_factory=list, description="示例查询 (中文)"
    )
    example_queries_en: list[str] = Field(
        default_factory=list, description="示例查询 (英文)"
    )


# ============================================================
# 可视化逻辑编排 (§32.6, Phase 7 reserved)
# ============================================================


class LogicNode(BaseModel):  # Phase 7 reserved
    """逻辑编排节点"""

    id: str = Field(..., description="节点唯一 ID")
    type: LogicNodeType = Field(..., description="节点类型")
    label: str = Field("", description="节点标签")
    config: dict[str, Any] = Field(default_factory=dict, description="节点配置")
    next_nodes: list[str] = Field(default_factory=list, description="下一个节点 ID 列表")
    condition_branches: dict[str, str] | None = Field(
        None, description="条件分支 (condition 节点, value→next_node_id)"
    )


class LogicFlow(BaseModel):  # Phase 7 reserved
    """可视化逻辑编排 (Service Hooks 的可视化版)"""

    hook: str = Field(..., description="钩子名称 (如 before_create)")
    nodes: list[LogicNode] = Field(default_factory=list, description="节点列表")
    entry_node_id: str | None = Field(None, description="入口节点 ID")
    description: str = Field("", description="流程描述")


# ============================================================
# 顶层配置: CrudConfig
# ============================================================


_MODULE_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
_TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


class CrudConfig(BaseModel):
    """CRUD 生成器顶层配置 (§3.1)"""

    # ---- 基本信息 (Step 1) ----
    module: str = Field(..., description="模块名 kebab-case (如 order)")
    table_name: str = Field(..., description="数据库表名 snake_case (如 orders)")

    @field_validator("module")
    @classmethod
    def validate_module(cls, v: str) -> str:
        if not _MODULE_RE.match(v):
            raise ValueError("module must be kebab-case (e.g. 'order' or 'order-item')")
        return v

    @field_validator("table_name")
    @classmethod
    def validate_table_name(cls, v: str) -> str:
        if not _TABLE_NAME_RE.match(v):
            raise ValueError("table_name must be snake_case (e.g. 'orders' or 'order_items')")
        return v

    display_name: str = Field(..., description="中文显示名")
    display_name_en: str = Field(..., description="英文显示名")
    scope: ScopeType = Field(ScopeType.TENANT, description="生成范围")
    parent_menu: str = Field(..., description="父菜单标识")
    description: str = Field("", description="模块描述")

    # ---- 选项 ----
    soft_delete: bool = Field(True, description="启用软删除")
    drag_sort: bool = Field(False, description="启用拖拽排序")
    has_status_toggle: bool = Field(True, description="列表 is_active 开关")
    recyclable: bool = Field(True, description="启用回收站")

    # ---- 字段定义 (Step 2) ----
    fields: list[FieldConfig] = Field(..., description="字段列表")

    # ---- 关联定义 (Step 1 高级) ----
    relations: list[RelationConfig] = Field(default_factory=list, description="关联关系")

    # ---- 搜索定义 (Step 2 高级) ----
    search_config: SearchConfig | None = Field(None, description="搜索栏配置")

    # ---- 枚举定义 ----
    enums: list[EnumDefinition] = Field(default_factory=list, description="枚举定义")

    # ---- 列表配置 (Step 3) ----
    list_config: ListConfig = Field(default_factory=ListConfig, description="列表配置")

    # ---- 表单配置 (Step 4) ----
    form_config: FormConfig = Field(default_factory=FormConfig, description="表单配置")

    # ---- 操作列 ----
    operations: list[str] = Field(
        default_factory=lambda: ["edit", "delete"], description="操作列按钮"
    )

    # ---- 下拉选项 API ----
    selectable: SelectableConfig | None = Field(None, description="下拉选项 API 配置")

    # ---- 复合索引 ----
    indexes: list[IndexConfig] = Field(default_factory=list, description="复合索引")

    # ---- 导入导出 ----
    import_export: ImportExportConfig | None = Field(None, description="导入导出配置")

    # ---- 权限 ----
    permissions: PermissionConfig | None = Field(None, description="权限配置")

    # ---- Service Hooks ----
    hooks: list[HookType] = Field(default_factory=list, description="Service 钩子")

    # ---- 自定义 Slot ----
    custom_slots: list[CustomSlotConfig] = Field(
        default_factory=list, description="自定义 Slot"
    )

    # ---- 布局 ----
    layout: LayoutConfig = Field(default_factory=LayoutConfig, description="布局配置")

    # ---- 样式 ----
    style: StyleConfig = Field(default_factory=StyleConfig, description="样式配置")

    # ---- 动画 ----
    animation: AnimationConfig = Field(
        default_factory=AnimationConfig, description="动画配置"
    )

    # ---- Git ----
    git: GitConfig = Field(default_factory=GitConfig, description="Git 集成")

    # ---- 审计 ----
    audit: AuditConfig = Field(default_factory=AuditConfig, description="审计配置")

    # ---- 测试 ----
    test: TestScaffoldConfig = Field(default_factory=TestScaffoldConfig, description="测试脚手架")

    # ---- 行内编辑 ----
    inline_edit: InlineEditConfig = Field(
        default_factory=InlineEditConfig, description="行内编辑"
    )

    # ---- 可观测性 ----
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig, description="可观测性"
    )

    # ---- 自然语言查询 ----
    nl_query: NLQueryConfig = Field(
        default_factory=NLQueryConfig, description="自然语言查询"
    )

    # ---- 可视化逻辑编排 ----
    logic_flows: list[LogicFlow] = Field(
        default_factory=list, description="逻辑编排 (可视化 Service Hooks)"
    )


# ============================================================
# 多表批量生成
# ============================================================


class EntityRelation(BaseModel):
    """跨实体关联（BatchCrudProject 级别）

    描述两个实体之间的关联关系，generate_batch() 会将其
    注入到对应实体的 CrudConfig.relations 中。
    """

    source_entity: str = Field(..., description="源实体 module 名")
    target_entity: str = Field(..., description="目标实体 module 名")
    relation_type: RelationType = Field(..., description="关联类型")
    foreign_key: str | None = Field(None, description="外键字段名 (默认: {target}_id)")
    nullable: bool = Field(True, description="外键是否可为空")


class BatchCrudProject(BaseModel):
    """多表批量生成项目

    编排层 — 将 N 个 CrudConfig 组合为一个项目，
    支持跨表关联、共享枚举、依赖排序。
    每个实体仍是完整的单表 CrudConfig，批量不侵入单表 schema。
    """

    project_name: str = Field(..., description="项目/领域名称 (如 '订单管理')")
    description: str = Field("", description="业务描述")
    entities: list[CrudConfig] = Field(..., description="实体配置列表", min_length=1)
    cross_relations: list[EntityRelation] = Field(
        default_factory=list, description="跨表关联 (注入到各实体 relations)"
    )
    shared_enums: list[EnumDefinition] = Field(
        default_factory=list, description="共享枚举 (跨实体复用)"
    )
    generation_order: list[str] = Field(
        default_factory=list,
        description="推荐生成顺序 (module 名列表, 按依赖排序; 空则按 entities 顺序)",
    )
