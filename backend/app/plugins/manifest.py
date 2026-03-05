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

_FRONTEND_PLUGIN_ROUTE_PREFIXES = ("/admin/plugins/", "/tenant/plugins/")
_API_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_WEBHOOK_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE"}
_API_AUTH_VALUES = {"required", "none"}
_WEBHOOK_AUTH_VALUES = {"none", "hmac", "token", "signature"}
_PATH_PARAM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SOCKETIO_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_NPM_DEP_SPEC_PATTERN = re.compile(
    r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*(?:@[A-Za-z0-9._~^<>=*-]+)?$",
    re.IGNORECASE,
)
_DB_TABLE_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}_$")
# Handler 路径：点分隔的 Python 模块路径，如 "api.handlers.handle_current"
# 允许字母、数字、下划线和点；禁止 .. / \ 等路径遍历字符
_HANDLER_PATH_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _validate_handler_path(v: str, field_name: str = "handler") -> str:
    """Handler 模块路径校验：防止路径遍历和非法字符（如 ../../etc）"""
    path = (v or "").strip()
    if not path:
        raise ValueError(f"{field_name} cannot be empty")
    if not _HANDLER_PATH_PATTERN.match(path):
        raise ValueError(
            f"{field_name} '{path}' is invalid. "
            f"Only letters, digits, underscores and dots are allowed "
            f"(e.g. 'api.handlers.my_handler')."
        )
    return path


def _validate_plugin_dependency_name(v: str) -> str:
    """插件依赖名称校验（小写 kebab-case）"""
    name = (v or "").strip()
    if not name:
        raise ValueError("dependencies.plugins item cannot be empty")
    if not _PLUGIN_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid plugin dependency name '{name}'. "
            "Must be lowercase kebab-case (e.g. 'crm-module')."
        )
    return name


def _validate_npm_dependency_spec(v: str) -> str:
    """npm 依赖规格校验，拒绝 CLI 注入字符与非法格式"""
    spec = (v or "").strip()
    if not spec:
        raise ValueError("npm_dependencies item cannot be empty")
    if spec.startswith("-"):
        raise ValueError(f"Invalid npm dependency '{spec}': cannot start with '-'")

    # 禁止 shell 元字符和空白（避免命令注入）
    forbidden = {" ", "\t", "\n", "\r", ";", "&", "|", "`", "$", "\\", "\"", "'"}
    if any(ch in spec for ch in forbidden):
        raise ValueError(
            f"Invalid npm dependency '{spec}': contains forbidden characters"
        )

    if not _NPM_DEP_SPEC_PATTERN.match(spec):
        raise ValueError(
            f"Invalid npm dependency '{spec}'. "
            "Expected format: 'name', 'name@version', '@scope/name' or '@scope/name@version'."
        )
    return spec


def _validate_frontend_plugin_route_path(path: str) -> str:
    """前端插件路由必须位于 /admin/plugins/* 或 /tenant/plugins/* 下。"""
    if not any(path.startswith(prefix) for prefix in _FRONTEND_PLUGIN_ROUTE_PREFIXES):
        raise ValueError(
            "Frontend plugin route path must start with '/admin/plugins/' "
            "or '/tenant/plugins/'"
        )
    return path


def _normalize_extension_path(
    path: str,
    *,
    field_name: str,
    keep_leading_slash: bool,
    allow_path_params: bool = True,
) -> str:
    """扩展点路径规范化与安全校验。"""
    normalized = (path or "").strip().replace("\\", "/")
    normalized = normalized.strip("/")
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")

    for segment in normalized.split("/"):
        if segment in {"", ".", ".."}:
            raise ValueError(f"{field_name} contains illegal segment '{segment}'")

        if segment.startswith("{") and segment.endswith("}"):
            if not allow_path_params:
                raise ValueError(f"{field_name} does not allow path parameters")
            param_name = segment[1:-1].strip()
            if not _PATH_PARAM_NAME_PATTERN.match(param_name):
                raise ValueError(
                    f"{field_name} contains invalid path parameter name '{param_name}'"
                )
            continue

        if "{" in segment or "}" in segment:
            raise ValueError(f"{field_name} contains malformed parameter segment '{segment}'")

    return f"/{normalized}" if keep_leading_slash else normalized


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

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        if not v:  # entry_point 是可选的
            return v
        return _validate_handler_path(v, "skill.entry_point")


class AdapterExtensionSchema(BaseModel):
    """AI 适配器扩展声明"""

    provider_code: str
    display_name: I18nText = Field(default_factory=dict)
    entry_point: str
    supported_models: list[str] = Field(default_factory=list)

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        return _validate_handler_path(v, "adapter.entry_point")


class StorageDriverExtensionSchema(BaseModel):
    """存储驱动扩展声明"""

    code: str
    display_name: I18nText = Field(default_factory=dict)
    entry_point: str

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        return _validate_handler_path(v, "storage_driver.entry_point")


class ApiRouteSchema(BaseModel):
    """API 路由声明"""

    method: str = "GET"
    path: str
    handler: str
    summary: str = ""
    auth: str = "required"
    permission: str = ""

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "api.handler")

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        method = v.strip().upper()
        if method not in _API_HTTP_METHODS:
            raise ValueError(
                f"Invalid API method '{v}'. Must be one of: {sorted(_API_HTTP_METHODS)}"
            )
        return method

    @field_validator("auth")
    @classmethod
    def validate_auth(cls, v: str) -> str:
        auth = v.strip().lower()
        if auth not in _API_AUTH_VALUES:
            raise ValueError(
                f"Invalid API auth '{v}'. Must be one of: {sorted(_API_AUTH_VALUES)}"
            )
        return auth

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return _normalize_extension_path(
            v,
            field_name="api.path",
            keep_leading_slash=False,
            allow_path_params=True,
        )


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

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "hook.handler")


class TaskExtensionSchema(BaseModel):
    """定时任务扩展声明"""

    name: str
    handler: str
    schedule_type: str = "interval"
    cron_expression: str | None = None
    interval_seconds: int | None = None
    queue: str = "default"
    description: str = ""

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "task.handler")


class MiddlewareExtensionSchema(BaseModel):
    """插件 ASGI 中间件扩展声明

    插件可声明一个 ASGI 中间件，在应用启动时注入请求链。
    中间件在插件启用时注册，禁用时标记为待优化（完全移除需重启服务）。

    handler 必须是一个 ASGI 中间件工厂类，接收 app 参数并返回中间件实例：

    ```python
    class MyMiddleware:
        def __init__(self, app): self.app = app
        async def __call__(self, scope, receive, send): ...
    ```
    """

    name: str
    handler: str
    priority: int = 50
    description: str = ""

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "middleware.handler")


class CustomExtensionSchema(BaseModel):
    """通用自定义扩展点声明

    为插件提供对未预见扩展类型的支持。
    框架将 custom 扩展的元数据存入内存注册表，
    插件可通过 PluginContext 或其他插件关联读取。

    用途示例：
    - 平台专属功能特性声明
    - 跨插件元数据注册（如 CRM 插件提供客户字段扩展点）
    - 延迟加载配置和功能开关
    """

    type: str
    name: str
    data: dict = Field(default_factory=dict)
    description: str = ""


class ConsumerExtensionSchema(BaseModel):
    """消息队列消费者扩展声明

    区别于 tasks（带调度的定时任务），consumers 是纯事件驱动的 Celery worker，
    由队列消息触发，无 Celery Beat 调度。
    """

    name: str
    handler: str
    queue: str = "default"
    description: str = ""
    max_retries: int = 3
    retry_delay: int = 60

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "consumer.handler")


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
    scope: str = "all_tenants"
    actions: list[str] = Field(default_factory=list)


# ── 前端扩展 ──


class MenuExtensionSchema(BaseModel):
    """菜单扩展声明

    菜单是导航链接，指向已有路由，不创建新路由，
    因此不限制 path 必须在 /admin/plugins/ 下。
    """

    name: str
    path: str
    icon: str = ""
    parent: str | None = None
    sort_order: int = 100
    scope: str = "admin_only"
    component: str = ""
    title: I18nText = Field(default_factory=dict)
    hidden: bool = False


class HeaderWidgetSchema(BaseModel):
    """头部小部件扩展"""

    name: str
    component: str
    sort_order: int = 100
    scope: str = ""


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

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return _validate_frontend_plugin_route_path(v)


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
    scope: str = "all_tenants"


class SettingsTabSchema(BaseModel):
    """设置页签扩展"""

    name: str
    component: str
    title: I18nText = Field(default_factory=dict)
    scope: str = "all_tenants"


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
    npm_dependencies: list[str] = Field(default_factory=list)

    @field_validator("npm_dependencies")
    @classmethod
    def validate_npm_dependencies(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for dep in v:
            cleaned.append(_validate_npm_dependency_spec(dep))
        return list(dict.fromkeys(cleaned))


# ── Socket.IO Namespace ──


class SocketIONamespaceSchema(BaseModel):
    """Socket.IO namespace 扩展声明

    插件可声明一个或多个 Socket.IO namespace，
    启用时动态注册到 AsyncServer，禁用/卸载时反注册。

    namespace 路径自动添加 /plugin/{plugin_name}/ 前缀，
    避免与系统内置 namespace（/admin, /tenant, /user）冲突。
    """

    path: str = Field(
        ...,
        description="Namespace 路径（不含 /plugin/{name}/ 前缀，如 'collab'）",
    )
    handler: str = Field(
        ...,
        description="Handler 模块路径（相对于 backend/，如 'sio.collab_ns.CollabNamespace'）",
    )
    auth_required: bool = Field(
        default=True,
        description="是否需要 JWT 认证",
    )
    auth_scopes: list[str] = Field(
        default_factory=lambda: ["tenant_admin"],
        description="允许的 token scope 列表（tenant_admin / tenant_user / admin）",
    )
    description: str = ""

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "socketio.handler")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        normalized = _normalize_extension_path(
            v,
            field_name="socketio.path",
            keep_leading_slash=False,
            allow_path_params=False,
        )
        for segment in normalized.split("/"):
            if not _SOCKETIO_SEGMENT_PATTERN.match(segment):
                raise ValueError(
                    "socketio.path can only contain letters, numbers, '_' and '-'"
                )
        return normalized


# ── Webhook + EventBus (v7) ──


class WebhookAuthSchema(BaseModel):
    """Webhook 认证配置"""

    type: str = "hmac"
    secret_config_key: str = ""
    header_name: str = "X-Webhook-Signature"

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        auth_type = v.strip().lower()
        if auth_type not in _WEBHOOK_AUTH_VALUES:
            raise ValueError(
                "Invalid webhook auth type "
                f"'{v}'. Must be one of: {sorted(_WEBHOOK_AUTH_VALUES)}"
            )
        return auth_type


class WebhookExtensionSchema(BaseModel):
    """Webhook 端点扩展声明"""

    path: str
    handler: str
    method: str = "POST"
    auth: WebhookAuthSchema = Field(default_factory=WebhookAuthSchema)
    description: str = ""

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "webhook.handler")

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        method = v.strip().upper()
        if method not in _WEBHOOK_HTTP_METHODS:
            raise ValueError(
                "Invalid webhook method "
                f"'{v}'. Must be one of: {sorted(_WEBHOOK_HTTP_METHODS)}"
            )
        return method

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return _normalize_extension_path(
            v,
            field_name="webhook.path",
            keep_leading_slash=True,
            allow_path_params=True,
        )


class EventExtensionSchema(BaseModel):
    """EventBus 事件订阅声明"""

    event: str
    handler: str

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "event.handler")


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
    socketio: list[SocketIONamespaceSchema] = Field(default_factory=list)
    consumers: list[ConsumerExtensionSchema] = Field(default_factory=list)
    custom: list[CustomExtensionSchema] = Field(default_factory=list)
    middleware: list[MiddlewareExtensionSchema] = Field(default_factory=list)


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

    @field_validator("python")
    @classmethod
    def validate_python_dependencies(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for req in v:
            req_str = (req or "").strip()
            if not req_str:
                raise ValueError("dependencies.python item cannot be empty")
            try:
                from packaging.requirements import Requirement

                parsed = Requirement(req_str)
            except Exception as exc:
                raise ValueError(
                    f"Invalid python dependency '{req_str}': {exc}"
                ) from exc
            if parsed.url:
                raise ValueError(
                    f"Direct URL python dependency is not allowed: '{req_str}'"
                )
            cleaned.append(req_str)
        return list(dict.fromkeys(cleaned))

    @field_validator("plugins")
    @classmethod
    def validate_plugin_dependencies(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for dep in v:
            cleaned.append(_validate_plugin_dependency_name(dep))
        return list(dict.fromkeys(cleaned))


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

_NAME_PATTERN = _PLUGIN_NAME_PATTERN
_VALID_SCOPES = {e.value for e in PluginScopeEnum}

# 已定义的插件能力白名单（与 PluginContext._require() 中使用的字符串对齐）
# 新增能力时需要同步更新此集合
_VALID_CAPABILITIES: frozenset[str] = frozenset({
    "db:read",           # 读取数据库（自有表）
    "db:write",          # 写入数据库（自有表）
    "db:own_tables",     # 操作自有 px_ 数据表（含 read+write）
    "http:outbound",     # 发送外部 HTTP 请求（含 SSRF 防护）
    "storage:read",      # 读取存储文件
    "storage:write",     # 写入存储文件
    "ai:call",           # 调用 AI 功能（via SystemAgentAssignment）
    "config:write",      # 修改插件自身配置
    "notifications:send",# 发送通知 / WebSocket 推送
})


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
    db_table_prefixes: list[str] = Field(default_factory=list)
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

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str]) -> list[str]:
        """capabilities 只允许已定义的白名单能力字符串"""
        unknown = [cap for cap in v if cap not in _VALID_CAPABILITIES]
        if unknown:
            raise ValueError(
                f"Unknown capabilities: {unknown}. "
                f"Valid capabilities: {sorted(_VALID_CAPABILITIES)}"
            )
        return list(dict.fromkeys(v))  # 去重保序

    @field_validator("db_table_prefixes")
    @classmethod
    def validate_db_table_prefixes(cls, v: list[str]) -> list[str]:
        """自定义 DB 表前缀白名单（可选），用于兼容历史前缀插件。"""
        normalized: list[str] = []
        for item in v:
            prefix = (item or "").strip()
            if not prefix:
                raise ValueError("db_table_prefixes item cannot be empty")
            if not _DB_TABLE_PREFIX_PATTERN.match(prefix):
                raise ValueError(
                    f"Invalid db_table_prefix '{prefix}'. "
                    "Expected lowercase prefix ending with '_' (e.g. 'ncc_')."
                )
            normalized.append(prefix)
        return list(dict.fromkeys(normalized))
