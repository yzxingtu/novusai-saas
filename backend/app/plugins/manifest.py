"""
插件清单 (plugin.yaml) Pydantic Schema

解析和校验 plugin.yaml 文件，将 YAML 内容转换为类型安全的 Python 对象。
"""

import re

from pydantic import BaseModel, Field, field_validator

from app.enums.plugin import PluginScopeEnum


# ── 类型别名 ──
I18nText = dict[str, str]
"""多语言文本，如 {"zh-CN": "CRM 管理", "en": "CRM Management"}"""


# ============================================================
# 扩展点子 Schema
# ============================================================


class SkillExtensionSchema(BaseModel):
    """技能扩展声明"""

    name: str
    type: str = "toolkit"
    display_name: I18nText = Field(default_factory=dict)
    description: I18nText = Field(default_factory=dict)
    entry_point: str = ""
    config_schema: dict | None = None


class AdapterExtensionSchema(BaseModel):
    """AI 适配器扩展声明"""

    provider_code: str
    display_name: I18nText = Field(default_factory=dict)
    entry_point: str
    supported_models: list[str] = Field(default_factory=list)


class StorageDriverExtensionSchema(BaseModel):
    """存储驱动扩展声明"""

    code: str
    display_name: I18nText = Field(default_factory=dict)
    entry_point: str


class ApiRouteSchema(BaseModel):
    """API 路由声明"""

    method: str = "GET"
    path: str
    handler: str
    summary: str = ""
    auth: str = "required"


class ApiExtensionSchema(BaseModel):
    """API 扩展声明"""

    admin_routes: list[ApiRouteSchema] = Field(default_factory=list)
    tenant_routes: list[ApiRouteSchema] = Field(default_factory=list)
    public_routes: list[ApiRouteSchema] = Field(default_factory=list)


class HookExtensionSchema(BaseModel):
    """Hook 扩展声明（同步拦截）"""

    point: str
    handler: str
    priority: int = 50
    description: str = ""


class TaskExtensionSchema(BaseModel):
    """定时任务扩展声明"""

    name: str
    handler: str
    schedule_type: str = "interval"
    cron_expression: str | None = None
    interval_seconds: int | None = None
    queue: str = "default"
    description: str = ""


class NotificationExtensionSchema(BaseModel):
    """通知模板扩展声明"""

    code: str
    title: I18nText = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["ws", "inbox"])
    category: str = "biz"


class PermissionExtensionSchema(BaseModel):
    """权限扩展声明"""

    code: str
    name: I18nText = Field(default_factory=dict)
    scope: str = "tenant"
    actions: list[str] = Field(default_factory=list)


# ── 前端扩展 ──


class MenuExtensionSchema(BaseModel):
    """菜单扩展声明"""

    name: str
    path: str
    icon: str = ""
    parent: str | None = None
    sort_order: int = 100
    scope: str = "tenant"
    component: str = ""


class HeaderWidgetSchema(BaseModel):
    """头部小部件扩展"""

    name: str
    component: str
    sort_order: int = 100


class FloatingPanelSchema(BaseModel):
    """浮动面板扩展"""

    name: str
    component: str
    icon: str = ""
    position: str = "bottom-right"


class StandalonePageSchema(BaseModel):
    """独立页面扩展"""

    name: str
    path: str
    component: str
    title: I18nText = Field(default_factory=dict)


class NotificationUIExtensionSchema(BaseModel):
    """通知 UI 扩展"""

    event: str
    component: str


class DashboardWidgetSchema(BaseModel):
    """仪表板组件扩展"""

    name: str
    component: str
    title: I18nText = Field(default_factory=dict)
    grid: dict = Field(default_factory=lambda: {"w": 6, "h": 4})
    scope: str = "tenant"


class SettingsTabSchema(BaseModel):
    """设置页签扩展"""

    name: str
    component: str
    title: I18nText = Field(default_factory=dict)
    scope: str = "tenant"


class FrontendSideSchema(BaseModel):
    """前端端侧声明（admin/tenant 共用结构）"""

    entry: str = ""
    styles: list[str] = Field(default_factory=list)


class FrontendExtensionSchema(BaseModel):
    """前端扩展总声明"""

    menus: list[MenuExtensionSchema] = Field(default_factory=list)
    header_widgets: list[HeaderWidgetSchema] = Field(default_factory=list)
    floating_panels: list[FloatingPanelSchema] = Field(default_factory=list)
    standalone_pages: list[StandalonePageSchema] = Field(default_factory=list)
    notification_ui: list[NotificationUIExtensionSchema] = Field(default_factory=list)
    dashboard_widgets: list[DashboardWidgetSchema] = Field(default_factory=list)
    settings_tabs: list[SettingsTabSchema] = Field(default_factory=list)
    admin: FrontendSideSchema = Field(default_factory=FrontendSideSchema)
    tenant: FrontendSideSchema = Field(default_factory=FrontendSideSchema)


# ── Webhook + EventBus (v7) ──


class WebhookAuthSchema(BaseModel):
    """Webhook 认证配置"""

    type: str = "hmac"
    secret_config_key: str = ""
    header_name: str = "X-Webhook-Signature"


class WebhookExtensionSchema(BaseModel):
    """Webhook 端点扩展声明"""

    path: str
    handler: str
    method: str = "POST"
    auth: WebhookAuthSchema = Field(default_factory=WebhookAuthSchema)
    description: str = ""


class EventExtensionSchema(BaseModel):
    """EventBus 事件订阅声明"""

    event: str
    handler: str


# ── Feature Flags (v7) ──


class FeatureSchema(BaseModel):
    """Feature Flag 声明"""

    code: str
    name: I18nText = Field(default_factory=dict)
    default: bool = True
    description: I18nText = Field(default_factory=dict)


# ── 兼容性矩阵 (v7) ──


class CompatibilityConflictSchema(BaseModel):
    """插件冲突声明"""

    plugin: str
    reason: I18nText = Field(default_factory=dict)


class CompatibilityRequireSchema(BaseModel):
    """插件依赖声明"""

    plugin: str
    version: str = "*"


class CompatibilitySchema(BaseModel):
    """兼容性矩阵"""

    platform_version: str = "*"
    conflicts: list[CompatibilityConflictSchema] = Field(default_factory=list)
    requires: list[CompatibilityRequireSchema] = Field(default_factory=list)


# ============================================================
# 汇总扩展点
# ============================================================


class ExtensionsSchema(BaseModel):
    """所有扩展点汇总"""

    skills: list[SkillExtensionSchema] = Field(default_factory=list)
    adapters: list[AdapterExtensionSchema] = Field(default_factory=list)
    storage_drivers: list[StorageDriverExtensionSchema] = Field(default_factory=list)
    api: ApiExtensionSchema = Field(default_factory=ApiExtensionSchema)
    hooks: list[HookExtensionSchema] = Field(default_factory=list)
    tasks: list[TaskExtensionSchema] = Field(default_factory=list)
    notifications: list[NotificationExtensionSchema] = Field(default_factory=list)
    permissions: list[PermissionExtensionSchema] = Field(default_factory=list)
    frontend: FrontendExtensionSchema = Field(default_factory=FrontendExtensionSchema)
    webhooks: list[WebhookExtensionSchema] = Field(default_factory=list)
    events: list[EventExtensionSchema] = Field(default_factory=list)


# ============================================================
# AI / 依赖 / 定价 / 资源 / 开发者
# ============================================================


class AIFeatureSchema(BaseModel):
    """AI 功能声明"""

    feature_code: str
    display_name: I18nText = Field(default_factory=dict)
    description: I18nText = Field(default_factory=dict)
    default_prompt: str = ""


class AIRequirementsSchema(BaseModel):
    """AI 需求声明"""

    features: list[AIFeatureSchema] = Field(default_factory=list)
    required_model_types: list[str] = Field(default_factory=list)
    min_context_window: int | None = None


class DependenciesSchema(BaseModel):
    """依赖声明"""

    python: list[str] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)
    system: list[str] = Field(default_factory=list)


class DeveloperSchema(BaseModel):
    """开发者信息"""

    name: str = ""
    email: str = ""
    url: str = ""


class TrialSchema(BaseModel):
    """试用期配置"""

    enabled: bool = False
    days: int = 14


class PricingSchema(BaseModel):
    """定价信息"""

    type: str = "free"
    price: float | None = None
    currency: str = "CNY"
    trial: TrialSchema = Field(default_factory=TrialSchema)


class ResourcesSchema(BaseModel):
    """资源声明"""

    readme: I18nText = Field(default_factory=dict)
    changelog: str = ""
    screenshots: list[str] = Field(default_factory=list)
    documentation_url: str = ""


# ============================================================
# 顶层 PluginManifest
# ============================================================

_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_VALID_SCOPES = {e.value for e in PluginScopeEnum}


class PluginManifest(BaseModel):
    """
    插件清单顶层 Schema

    对应 plugin.yaml 文件的完整结构。
    """

    # ── 必填 ──
    name: str = Field(..., max_length=100)
    version: str
    display_name: I18nText
    scope: str

    # ── 基本信息 ──
    description: I18nText = Field(default_factory=dict)
    author: str = ""
    icon: str = ""
    icon_color: str = ""
    banner: str = ""
    homepage: str = ""
    repository_url: str = ""
    license: str = ""
    tags: list[str] = Field(default_factory=list)

    # ── 开发者 ──
    developer: DeveloperSchema | None = None

    # ── 扩展点 ──
    extensions: ExtensionsSchema = Field(default_factory=ExtensionsSchema)

    # ── AI ──
    ai_requirements: AIRequirementsSchema = Field(
        default_factory=AIRequirementsSchema,
    )

    # ── 配置 ──
    config_schema: dict | None = None
    tenant_config_schema: dict | None = None

    # ── 依赖 ──
    dependencies: DependenciesSchema = Field(
        default_factory=DependenciesSchema,
    )

    # ── 定价 ──
    pricing: PricingSchema = Field(default_factory=PricingSchema)

    # ── 资源 ──
    resources: ResourcesSchema = Field(default_factory=ResourcesSchema)

    # ── v8 新增 ──
    capabilities: list[str] = Field(default_factory=list)
    api_version: str = "1"

    # ── v7 新增 ──
    features: list[FeatureSchema] = Field(default_factory=list)
    compatibility: CompatibilitySchema | None = None

    # ── 校验 ──

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """插件名必须为小写 kebab-case"""
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                "Plugin name must be lowercase kebab-case "
                "(e.g. 'crm-module', 'slack-integration')"
            )
        return v

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        """scope 必须是合法的 PluginScopeEnum 值"""
        if v not in _VALID_SCOPES:
            raise ValueError(
                f"Invalid scope '{v}'. Must be one of: {sorted(_VALID_SCOPES)}"
            )
        return v
