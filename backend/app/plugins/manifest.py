"""
Plugin manifest (plugin.yaml) Pydantic Schema. / 插件清单 (plugin.yaml) Pydantic Schema。

Parse and validate plugin.yaml files, converting YAML content into type-safe Python objects.
/ 解析和校验 plugin.yaml 文件，将 YAML 内容转换为类型安全的 Python 对象。
"""

from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums.agent import get_all_skill_types
from app.enums.common import ResourceScopeEnum
from app.plugins.manifest_helpers import (
    _API_AUTH_VALUES,
    _API_HTTP_METHODS,
    _DB_TABLE_PREFIX_PATTERN,
    _PLUGIN_NAME_PATTERN,
    _SOCKETIO_SEGMENT_PATTERN,
    _VALID_PLUGIN_ENDPOINT_SCOPES,
    _VALID_PLUGIN_PERMISSION_EXT_SCOPES,
    _WEBHOOK_AUTH_VALUES,
    _WEBHOOK_HTTP_METHODS,
    I18nText,
    _normalize_extension_path,
    _validate_frontend_plugin_route_path,
    _validate_handler_path,
)
from app.plugins.manifest_metadata_schemas import (
    AIFeatureSchema,
    AIRequirementsSchema,
    CompatibilityConflictSchema,
    CompatibilitySchema,
    DependenciesSchema,
    DeveloperSchema,
    FeatureSchema,
    PluginDependencySchema,
    PricingSchema,
    ResourcesSchema,
    TrialSchema,
)

__all__ = [
    "AIFeatureSchema",
    "AIRequirementsSchema",
    "CompatibilityConflictSchema",
    "CompatibilitySchema",
    "DependenciesSchema",
    "DeveloperSchema",
    "ExtensionsSchema",
    "FeatureSchema",
    "PluginDependencySchema",
    "PluginManifest",
    "PricingSchema",
    "ResourcesSchema",
    "TrialSchema",
]

# ============================================================
# Extension point sub-schemas / 扩展点子 Schema
# ============================================================


class SkillExtensionSchema(BaseModel):
    """Skill extension declaration / 技能扩展声明"""

    name: str = Field(..., max_length=100)
    type: str = Field("toolkit", max_length=30)
    display_name: I18nText = Field(default_factory=dict)
    description: I18nText = Field(default_factory=dict)
    entry_point: str
    config_schema: dict | None = None
    preview_tool_names: list[str] = Field(default_factory=list)
    preview_semantic_families: list[str] = Field(default_factory=list)

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        if not str(v or "").strip():
            raise ValueError("skill.entry_point is required")
        return _validate_handler_path(v, "skill.entry_point")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        text = str(v or "").strip()
        if not text:
            raise ValueError("skill.name is required")
        if not _PLUGIN_NAME_PATTERN.match(text):
            raise ValueError(
                "skill.name must be lowercase kebab-case (e.g. 'weather-realtime')"
            )
        return text

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        text = str(v or "").strip()
        if not text:
            raise ValueError("skill.type is required")
        valid_types = get_all_skill_types()
        if text not in valid_types:
            raise ValueError(
                f"Invalid skill.type '{text}'. Must be one of: {sorted(valid_types)}"
            )
        return text

    @field_validator("preview_tool_names", mode="before")
    @classmethod
    def validate_preview_tool_names(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("skill.preview_tool_names must be a list")

        normalized: list[str] = []
        for item in v:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    @field_validator("preview_semantic_families", mode="before")
    @classmethod
    def validate_preview_semantic_families(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("skill.preview_semantic_families must be a list")

        normalized: list[str] = []
        for item in v:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized


class AdapterExtensionSchema(BaseModel):
    """AI adapter extension declaration / AI 适配器扩展声明"""

    provider_code: str
    display_name: I18nText = Field(default_factory=dict)
    entry_point: str
    supported_models: list[str] = Field(default_factory=list)

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        return _validate_handler_path(v, "adapter.entry_point")


class StorageDriverExtensionSchema(BaseModel):
    """Storage driver extension declaration / 存储驱动扩展声明"""

    code: str
    display_name: I18nText = Field(default_factory=dict)
    entry_point: str

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        return _validate_handler_path(v, "storage_driver.entry_point")


class ApiRouteSchema(BaseModel):
    """API route declaration / API 路由声明"""

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
    """API extension declaration / API 扩展声明"""

    admin_routes: list[ApiRouteSchema] = Field(default_factory=list)
    tenant_routes: list[ApiRouteSchema] = Field(default_factory=list)
    public_routes: list[ApiRouteSchema] = Field(default_factory=list)


class HookExtensionSchema(BaseModel):
    """Hook extension declaration (synchronous interception) / Hook 扩展声明（同步拦截）"""

    point: str
    handler: str
    priority: int = 50
    description: str = ""

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "hook.handler")


class TaskExtensionSchema(BaseModel):
    """Periodic task extension declaration / 定时任务扩展声明"""

    name: str
    handler: str
    display_name: I18nText = Field(default_factory=dict)
    schedule_type: str = "interval"
    cron_expression: str | None = None
    interval_seconds: int | None = None
    queue: str = "default"
    description: I18nText = Field(default_factory=dict)

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "task.handler")


class MiddlewareExtensionSchema(BaseModel):
    """Plugin ASGI middleware extension declaration.
    / 插件 ASGI 中间件扩展声明

    Plugins can declare an ASGI middleware, injected into the request chain by the host runtime.
    Middleware is registered on plugin enable and removed on disable by rebuilding the runtime stack.
    / 插件可声明一个 ASGI 中间件，由宿主运行时注入请求链。
    中间件在插件启用时注册，禁用时会通过重建运行时栈移除。

    handler must be an ASGI middleware factory class that accepts app and returns a middleware instance:
    / handler 必须是一个 ASGI 中间件工厂类：

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
    """Generic custom extension point declaration.
    / 通用自定义扩展点声明

    Provides support for unforeseen extension types.
    The framework stores custom extension metadata in an in-memory registry,
    accessible via PluginContext or cross-plugin associations.
    / 为插件提供对未预见扩展类型的支持。
    框架将 custom 扩展的元数据存入内存注册表。

    Use cases:
    - Platform-specific feature declarations
    - Cross-plugin metadata registry (e.g. CRM plugin providing customer field extension points)
    - Lazy-loaded config and feature flags
    / 用途示例：
    - 平台专属功能特性声明
    - 跨插件元数据注册
    - 延迟加载配置和功能开关
    """

    type: str
    name: str
    data: dict = Field(default_factory=dict)
    description: str = ""


class ConsumerExtensionSchema(BaseModel):
    """Message queue consumer extension declaration.
    / 消息队列消费者扩展声明

    Unlike tasks (scheduled periodic tasks), consumers are pure event-driven Celery workers,
    triggered by queue messages, without Celery Beat scheduling.
    / 区别于 tasks（带调度的定时任务），consumers 是纯事件驱动的 Celery worker。
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
    """Notification template extension declaration / 通知模板扩展声明"""

    code: str
    title: I18nText = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["ws", "inbox"])
    category: str = "biz"


class PermissionExtensionSchema(BaseModel):
    """Permission extension declaration / 权限扩展声明

    scope 为权限端别（与 ResourceScopeEnum 无关）：admin / tenant / both。
    """

    code: str
    name: I18nText = Field(default_factory=dict)
    scope: str = "tenant"
    actions: list[str] = Field(default_factory=list)

    @field_validator("scope", mode="before")
    @classmethod
    def _normalize_permission_ext_scope(cls, v: object) -> str:
        raw = "tenant" if v is None else str(v).strip()
        if raw not in _VALID_PLUGIN_PERMISSION_EXT_SCOPES:
            raise ValueError(
                f"Invalid permission scope '{v}'. Expected one of: admin|tenant|both."
            )
        return raw


# ── Frontend extensions / 前端扩展 ──


class MenuExtensionSchema(BaseModel):
    """Menu extension declaration.
    / 菜单扩展声明

    Menus are navigation links pointing to existing routes, not creating new routes,
    so path is not restricted to /admin/plugins/.
    / 菜单是导航链接，指向已有路由，不创建新路由。

    scope 为挂载端别：admin / tenant / both（与资源作用域无关）。
    """

    name: str
    path: str
    icon: str = ""
    parent: str | None = None
    sort_order: int = 100
    scope: str = "admin"
    component: str = ""
    title: I18nText = Field(default_factory=dict)
    hidden: bool = False

    @field_validator("scope", mode="before")
    @classmethod
    def _normalize_menu_scope(cls, v: object) -> str:
        raw = "admin" if v is None else str(v).strip()
        if raw not in _VALID_PLUGIN_ENDPOINT_SCOPES:
            raise ValueError(
                f"Invalid menu scope '{v}'. Expected one of: admin|tenant|both."
            )
        return raw


class HeaderWidgetSchema(BaseModel):
    """Header widget extension / 头部小部件扩展"""

    name: str
    component: str
    sort_order: int = 100
    scope: str = ""

    @field_validator("scope", mode="before")
    @classmethod
    def _normalize_header_scope(cls, v: object) -> str:
        if v is None:
            return ""
        raw = str(v).strip()
        if not raw:
            return ""
        if raw not in _VALID_PLUGIN_ENDPOINT_SCOPES:
            raise ValueError(
                f"Invalid header widget scope '{v}'. Expected one of: admin|tenant|both."
            )
        return raw


class FloatingPanelSchema(BaseModel):
    """Floating panel extension / 浮动面板扩展"""

    name: str
    component: str
    icon: str = ""
    position: str = "bottom-right"


class FrontendPageAISchema(BaseModel):
    """Frontend AI entry metadata (optional) / 前端 AI 入口元信息（可选）"""

    mode: Literal["disabled", "enabled"] | None = Field(
        None,
        description="AI chat visibility override: disabled / enabled",
    )


class FrontendPageMenuSchema(BaseModel):
    """Frontend page-derived menu declaration. / 前端页面派生菜单声明。"""

    parent: str | None = None
    sort_order: int = 100
    icon: str = ""
    hidden: bool = False
    title: I18nText = Field(default_factory=dict)


class FrontendPageSchema(BaseModel):
    """Frontend page declaration (single source for page + menu). / 前端页面声明（页面与菜单的单一事实来源）。"""

    name: str
    path: str
    component: str
    scope: Literal["admin", "tenant"]
    icon: str = ""
    title: I18nText = Field(default_factory=dict)
    access_codes: list[str] = Field(
        default_factory=list,
        description="Optional route access codes enforced by host frontend router guard",
    )
    menu: FrontendPageMenuSchema | None = None
    ai: FrontendPageAISchema | None = Field(
        None,
        description="Page-level AI strategy (falls back to host default if not declared)",
    )

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        return _validate_frontend_plugin_route_path(v)

    @field_validator("scope")
    @classmethod
    def validate_scope(
        cls, v: Literal["admin", "tenant"]
    ) -> Literal["admin", "tenant"]:
        if v not in {"admin", "tenant"}:
            raise ValueError("frontend.pages[*].scope must be 'admin' or 'tenant'")
        return v

    @field_validator("component")
    @classmethod
    def validate_component(cls, v: str) -> str:
        component = (v or "").strip()
        if not component:
            raise ValueError("frontend.pages[*].component cannot be empty")
        return component

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        name = (v or "").strip()
        if not name:
            raise ValueError("frontend.pages[*].name cannot be empty")
        return name

    @field_validator("access_codes", mode="before")
    @classmethod
    def validate_access_codes(cls, v: object) -> list[str]:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("frontend.pages[*].access_codes must be a list")

        normalized: list[str] = []
        for item in v:
            code = str(item or "").strip()
            if not code:
                continue
            normalized.append(code)
        return normalized

    @model_validator(mode="after")
    def validate_scope_path_consistency(self) -> "FrontendPageSchema":
        expected_prefix = f"/{self.scope}/plugins/"
        if not self.path.startswith(expected_prefix):
            raise ValueError(
                f"frontend.pages[*].path must match scope prefix '{expected_prefix}'"
            )
        return self


class NotificationUIExtensionSchema(BaseModel):
    """Notification UI extension / 通知 UI 扩展"""

    event: str
    component: str


class DashboardWidgetSchema(BaseModel):
    """Dashboard widget extension / 仪表板组件扩展"""

    name: str
    component: str
    title: I18nText = Field(default_factory=dict)
    grid: dict = Field(default_factory=lambda: {"w": 6, "h": 4})
    scope: str = "tenant"

    @field_validator("scope", mode="before")
    @classmethod
    def _normalize_dashboard_scope(cls, v: object) -> str:
        raw = "tenant" if v is None else str(v).strip()
        if raw not in _VALID_PLUGIN_ENDPOINT_SCOPES:
            raise ValueError(
                f"Invalid dashboard widget scope '{v}'. Expected one of: admin|tenant|both."
            )
        return raw


class SettingsTabSchema(BaseModel):
    """Settings tab extension / 设置页签扩展"""

    name: str
    component: str
    title: I18nText = Field(default_factory=dict)
    scope: str = "tenant"

    @field_validator("scope", mode="before")
    @classmethod
    def _normalize_settings_tab_scope(cls, v: object) -> str:
        raw = "tenant" if v is None else str(v).strip()
        if raw not in _VALID_PLUGIN_ENDPOINT_SCOPES:
            raise ValueError(
                f"Invalid settings tab scope '{v}'. Expected one of: admin|tenant|both."
            )
        return raw


class FrontendDevSchema(BaseModel):
    """Frontend dev source contract. / 前端开发态源码契约。"""

    entry: str = "src/index.ts"

    @field_validator("entry")
    @classmethod
    def validate_entry(cls, v: str) -> str:
        path = PurePosixPath(str(v or "").strip().replace("\\", "/").lstrip("/"))
        if str(path) in {"", "."} or ".." in path.parts:
            raise ValueError("frontend.dev.entry must be a safe relative path")
        return str(path)


class FrontendReleaseSchema(BaseModel):
    """Frontend production release contract. / 前端生产态发布契约。"""

    manifest: str = "plugin.manifest.json"

    @field_validator("manifest")
    @classmethod
    def validate_manifest(cls, v: str) -> str:
        path = PurePosixPath(str(v or "").strip().replace("\\", "/").lstrip("/"))
        if str(path) in {"", "."} or ".." in path.parts:
            raise ValueError("frontend.release.manifest must be a safe relative path")
        return str(path)


class FrontendExtensionSchema(BaseModel):
    """Frontend extension aggregate declaration / 前端扩展总声明"""

    pages: list[FrontendPageSchema] = Field(default_factory=list)
    header_widgets: list[HeaderWidgetSchema] = Field(default_factory=list)
    floating_panels: list[FloatingPanelSchema] = Field(default_factory=list)
    notification_ui: list[NotificationUIExtensionSchema] = Field(default_factory=list)
    dashboard_widgets: list[DashboardWidgetSchema] = Field(default_factory=list)
    settings_tabs: list[SettingsTabSchema] = Field(default_factory=list)
    dev: FrontendDevSchema = Field(default_factory=FrontendDevSchema)
    release: FrontendReleaseSchema = Field(default_factory=FrontendReleaseSchema)


# ── Socket.IO Namespace / Socket.IO 命名空间 ──


class SocketIONamespaceSchema(BaseModel):
    """Socket.IO namespace extension declaration.
    / Socket.IO namespace 扩展声明

    Plugins can declare one or more Socket.IO namespaces,
    dynamically registered to AsyncServer on enable, unregistered on disable/uninstall.
    / 插件可声明一个或多个 Socket.IO namespace。

    Namespace path automatically prefixed with /plugin/{plugin_name}/,
    avoiding conflicts with built-in namespaces (/admin, /tenant, /user).
    / namespace 路径自动添加 /plugin/{plugin_name}/ 前缀。
    """

    path: str = Field(
        ...,
        description="Namespace path (without /plugin/{name}/ prefix, e.g. 'collab')",
    )
    handler: str = Field(
        ...,
        description="Handler module path (relative to backend/, e.g. 'sio.collab_ns.CollabNamespace')",
    )
    auth_required: bool = Field(
        default=True,
        description="Whether JWT authentication is required",
    )
    auth_scopes: list[str] = Field(
        default_factory=lambda: ["tenant_admin"],
        description="Allowed token scope list (tenant_admin / tenant_user / admin)",
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


# ── Webhook + EventBus (v7) / Webhook + 事件总线 ──


class WebhookAuthSchema(BaseModel):
    """Webhook authentication configuration / Webhook 认证配置"""

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
    """Webhook endpoint extension declaration / Webhook 端点扩展声明"""

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
    """EventBus event subscription declaration / EventBus 事件订阅声明"""

    event: str
    handler: str

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: str) -> str:
        return _validate_handler_path(v, "event.handler")


class ExtensionsSchema(BaseModel):
    """All extension points aggregate / 所有扩展点汇总"""

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

    @model_validator(mode="after")
    def validate_unique_skill_names(self) -> "ExtensionsSchema":
        seen: set[str] = set()
        duplicates: list[str] = []
        for skill in self.skills:
            if skill.name in seen:
                duplicates.append(skill.name)
            seen.add(skill.name)
        if duplicates:
            raise ValueError(
                "extensions.skills[*].name must be unique within a plugin: "
                f"{sorted(set(duplicates))}"
            )
        return self


# ============================================================
# Top-level PluginManifest / 顶层 PluginManifest
# ============================================================

_NAME_PATTERN = _PLUGIN_NAME_PATTERN
_VALID_SCOPES = {e.value for e in ResourceScopeEnum}

# Defined plugin capabilities whitelist (aligned with strings used in PluginContext._require())
# New capabilities must be added to this set
# / 已定义的插件能力白名单（与 PluginContext._require() 中使用的字符串对齐）
# 新增能力时需要同步更新此集合
_VALID_CAPABILITIES: frozenset[str] = frozenset(
    {
        "db:read",  # Read database (own tables) / 读取数据库（自有表）
        "db:write",  # Write database (own tables) / 写入数据库（自有表）
        "db:own_tables",  # Operate own px_ tables (includes read+write) / 操作自有 px_ 数据表
        "platform:read",  # Read host snapshots via sandbox facade / 通过沙箱门面读取宿主快照
        "http:outbound",  # Send outbound HTTP requests (with SSRF protection) / 发送外部 HTTP 请求
        "storage:read",  # Read storage files / 读取存储文件
        "storage:write",  # Write storage files / 写入存储文件
        "ai:call",  # Call AI features (via SystemAgentAssignment) / 调用 AI 功能
        "config:write",  # Modify plugin's own config / 修改插件自身配置
        "notifications:send",  # Send notifications / WebSocket push / 发送通知
    }
)


class PluginManifest(BaseModel):
    """
    Plugin manifest top-level schema.
    / 插件清单顶层 Schema

    Corresponds to the complete structure of plugin.yaml.
    / 对应 plugin.yaml 文件的完整结构。
    """

    model_config = ConfigDict(extra="forbid")

    # ── Required / 必填 ──
    name: str = Field(..., max_length=100)
    version: str
    display_name: I18nText
    scope: str

    # ── Basic info / 基本信息 ──
    description: I18nText = Field(default_factory=dict)
    author: str = ""
    icon: str = ""
    icon_color: str = ""
    banner: str = ""
    homepage: str = ""
    repository_url: str = ""
    license: str = ""
    tags: list[str] = Field(default_factory=list)

    # ── Developer / 开发者 ──
    developer: DeveloperSchema | None = None

    # ── Extensions / 扩展点 ──
    extensions: ExtensionsSchema = Field(default_factory=ExtensionsSchema)

    # ── AI / 智能体依赖与能力 ──
    ai_requirements: AIRequirementsSchema = Field(
        default_factory=AIRequirementsSchema,
    )

    # ── Config / 配置 ──
    config_schema: dict | None = None
    tenant_config_schema: dict | None = None

    # ── Dependencies / 依赖 ──
    dependencies: DependenciesSchema = Field(
        default_factory=DependenciesSchema,
    )

    # ── Pricing / 定价 ──
    pricing: PricingSchema = Field(default_factory=PricingSchema)

    # ── Resources / 资源 ──
    resources: ResourcesSchema = Field(default_factory=ResourcesSchema)

    # ── v8 additions / v8 新增 ──
    capabilities: list[str] = Field(default_factory=list)
    db_table_prefixes: list[str] = Field(default_factory=list)
    api_version: str = "1"

    # ── v7 additions / v7 新增 ──
    features: list[FeatureSchema] = Field(default_factory=list)
    compatibility: CompatibilitySchema | None = None

    # ── Validation / 校验 ──

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Plugin name must be lowercase kebab-case / 插件名必须为小写 kebab-case"""
        if not _NAME_PATTERN.match(v):
            raise ValueError(
                "Plugin name must be lowercase kebab-case "
                "(e.g. 'crm-module', 'slack-integration')"
            )
        return v

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        """scope must be a valid ResourceScopeEnum value / scope 必须是合法的资源作用域值"""
        if v not in _VALID_SCOPES:
            raise ValueError(
                f"Invalid scope '{v}'. Must be one of: {sorted(_VALID_SCOPES)}"
            )
        return v

    @field_validator("icon")
    @classmethod
    def validate_plugin_metadata_icon(cls, v: str) -> str:
        """Plugin metadata icon only allows empty or root icon.png.
        / 插件元数据图标只允许留空或根目录 icon.png。"""
        raw = (v or "").strip()
        if not raw:
            return ""
        if raw != "icon.png":
            raise ValueError(
                "Plugin metadata icon must be empty or 'icon.png'. "
                "Use lucide icons only for frontend page/menu functional icons."
            )
        return raw

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, v: list[str]) -> list[str]:
        """capabilities only allows defined whitelist capability strings
        / capabilities 只允许已定义的白名单能力字符串"""
        unknown = [cap for cap in v if cap not in _VALID_CAPABILITIES]
        if unknown:
            raise ValueError(
                f"Unknown capabilities: {unknown}. "
                f"Valid capabilities: {sorted(_VALID_CAPABILITIES)}"
            )
        return list(dict.fromkeys(v))  # Deduplicate preserving order / 去重保序

    @field_validator("db_table_prefixes")
    @classmethod
    def validate_db_table_prefixes(cls, v: list[str]) -> list[str]:
        """Custom DB table prefix whitelist (optional), for backward-compatible legacy prefix plugins.
        / 自定义 DB 表前缀白名单（可选），用于兼容历史前缀插件。"""
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
