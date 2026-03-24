"""
Plugin manifest (plugin.yaml) Pydantic Schema. / 插件清单 (plugin.yaml) Pydantic Schema。

Parse and validate plugin.yaml files, converting YAML content into type-safe Python objects.
/ 解析和校验 plugin.yaml 文件，将 YAML 内容转换为类型安全的 Python 对象。
"""

import re
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.enums.common import ResourceScopeEnum
from app.plugins.dependencies import (
    PluginDependencyRequirement,
    combine_plugin_dependency_versions,
    validate_plugin_dependency_name,
    validate_plugin_dependency_version,
)

# ── Type aliases / 类型别名 ──
I18nText = dict[str, str]
"""Multilingual text, e.g. {"zh-CN": "CRM 管理", "en": "CRM Management"}. / 多语言文本。"""

# Plugin manifest menu/slot scope = endpoint side, not ResourceScopeEnum. / 插件菜单/插槽 scope 表端侧，非 ResourceScopeEnum
# Only canonical values are accepted; legacy aliases are no longer tolerated. / 仅接受规范取值，不再兼容历史别名
_VALID_PLUGIN_ENDPOINT_SCOPES = frozenset({"admin", "tenant", "both", ""})
_VALID_PLUGIN_PERMISSION_EXT_SCOPES = frozenset({"admin", "tenant", "both"})

_FRONTEND_PLUGIN_ROUTE_PREFIXES = ("/admin/plugins/", "/tenant/plugins/")
_API_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_WEBHOOK_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE"}
_API_AUTH_VALUES = {"required", "none"}
_WEBHOOK_AUTH_VALUES = {"none", "hmac", "token", "signature"}
_PATH_PARAM_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SOCKETIO_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_DB_TABLE_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,62}_$")
# Handler path: dot-separated Python module path, e.g. "api.handlers.handle_current"
# Allows letters, digits, underscores and dots; forbids .. / \ and other path traversal chars
# / Handler 路径：点分隔的 Python 模块路径
# 允许字母、数字、下划线和点；禁止 .. / \ 等路径遍历字符
_HANDLER_PATH_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


def _validate_handler_path(v: str, field_name: str = "handler") -> str:
    """Handler module path validation: prevent path traversal and illegal characters (e.g. ../../etc)
    / Handler 模块路径校验：防止路径遍历和非法字符"""
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


def _validate_frontend_plugin_route_path(path: str) -> str:
    """Frontend plugin routes must be under /admin/plugins/* or /tenant/plugins/*.
    / 前端插件路由必须位于 /admin/plugins/* 或 /tenant/plugins/* 下。"""
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
    """Extension point path normalization and security validation.
    / 扩展点路径规范化与安全校验。"""
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
# Extension point sub-schemas / 扩展点子 Schema
# ============================================================


class SkillExtensionSchema(BaseModel):
    """Skill extension declaration / 技能扩展声明"""

    name: str
    type: str = "toolkit"
    display_name: I18nText = Field(default_factory=dict)
    description: I18nText = Field(default_factory=dict)
    entry_point: str = ""
    config_schema: dict | None = None

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        if not v:  # entry_point is optional / entry_point 是可选的
            return v
        return _validate_handler_path(v, "skill.entry_point")


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
    """Plugin ASGI middleware extension declaration.
    / 插件 ASGI 中间件扩展声明

    Plugins can declare an ASGI middleware, injected into the request chain at app startup.
    Middleware is registered on plugin enable, marked for optimization on disable (full removal requires service restart).
    / 插件可声明一个 ASGI 中间件，在应用启动时注入请求链。
    中间件在插件启用时注册，禁用时标记为待优化（完全移除需重启服务）。

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
                f"Invalid permission scope '{v}'. "
                f"Expected one of: admin|tenant|both."
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
            raise ValueError(f"Invalid header widget scope '{v}'. Expected one of: admin|tenant|both.")
        return raw


class FloatingPanelSchema(BaseModel):
    """Floating panel extension / 浮动面板扩展"""

    name: str
    component: str
    icon: str = ""
    position: str = "bottom-right"


class FrontendPageAISchema(BaseModel):
    """Frontend page AI metadata (optional) / 前端页面 AI 元信息（可选）"""

    mode: Literal["disabled", "context_only", "operate"] | None = Field(
        None,
        description="AI mode override: disabled / context_only / operate",
    )
    page_context_key: str | None = Field(
        None,
        description="Page context registry key (for resolvePageContext exact matching)",
    )
    disabled_capabilities: list[str] | None = Field(
        None,
        description="Capability keys disabled on this page",
    )
    disabled_operations: list[str] | None = Field(
        None,
        description="Operation names disabled on this page",
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
    def validate_scope(cls, v: Literal["admin", "tenant"]) -> Literal["admin", "tenant"]:
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
                "frontend.pages[*].path must match scope prefix "
                f"'{expected_prefix}'"
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
            raise ValueError(f"Invalid dashboard widget scope '{v}'. Expected one of: admin|tenant|both.")
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
            raise ValueError(f"Invalid settings tab scope '{v}'. Expected one of: admin|tenant|both.")
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


# ── Feature Flags (v7) / 功能开关 ──


class FeatureSchema(BaseModel):
    """Feature flag declaration / Feature Flag 声明"""

    code: str
    name: I18nText = Field(default_factory=dict)
    default: bool = True
    description: I18nText = Field(default_factory=dict)


# ── Compatibility matrix (v7) / 兼容性矩阵 ──


class CompatibilityConflictSchema(BaseModel):
    """Plugin conflict declaration / 插件冲突声明"""

    plugin: str
    reason: I18nText = Field(default_factory=dict)


class CompatibilitySchema(BaseModel):
    """Compatibility matrix / 兼容性矩阵"""

    model_config = ConfigDict(extra="forbid")

    platform_version: str = "*"
    conflicts: list[CompatibilityConflictSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_requires(cls, data: object) -> object:
        if isinstance(data, dict) and "requires" in data:
            raise ValueError(
                "compatibility.requires has been removed. "
                "Use dependencies.plugins with optional version constraints instead."
            )
        return data


# ============================================================
# Aggregate extension points / 汇总扩展点
# ============================================================


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


# ============================================================
# AI / Dependencies / Pricing / Resources / Developer
# / AI / 依赖 / 定价 / 资源 / 开发者
# ============================================================


class AIFeatureSchema(BaseModel):
    """AI feature declaration / AI 功能声明"""

    feature_code: str
    display_name: I18nText = Field(default_factory=dict)
    description: I18nText = Field(default_factory=dict)
    default_prompt: str = ""


class AIRequirementsSchema(BaseModel):
    """AI requirements declaration / AI 需求声明"""

    features: list[AIFeatureSchema] = Field(default_factory=list)
    required_model_types: list[str] = Field(default_factory=list)
    min_context_window: int | None = None


class DependenciesSchema(BaseModel):
    """Dependencies declaration / 依赖声明"""

    model_config = ConfigDict(extra="forbid")

    python: list[str] = Field(default_factory=list)
    plugins: list["PluginDependencySchema"] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_system_dependencies(cls, data: object) -> object:
        if isinstance(data, dict) and "system" in data:
            raise ValueError(
                "dependencies.system is not supported in the unified runtime model. "
                "Move system prerequisites to documentation or typed preflight logic."
            )
        return data

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

    @field_validator("plugins", mode="before")
    @classmethod
    def normalize_plugin_dependencies(
        cls,
        v: object,
    ) -> list[dict[str, str]] | object:
        if not isinstance(v, list):
            return v

        normalized: list[dict[str, str]] = []
        for item in v:
            if isinstance(item, str):
                normalized.append(
                    {
                        "plugin": validate_plugin_dependency_name(item),
                        "version": "*",
                    }
                )
                continue
            normalized.append(item)
        return normalized

    @field_validator("plugins")
    @classmethod
    def deduplicate_plugin_dependencies(
        cls,
        v: list["PluginDependencySchema"],
    ) -> list["PluginDependencySchema"]:
        merged: dict[str, PluginDependencySchema] = {}
        for dep in v:
            existing = merged.get(dep.plugin)
            if existing is None:
                merged[dep.plugin] = dep
                continue
            merged[dep.plugin] = PluginDependencySchema(
                plugin=dep.plugin,
                version=combine_plugin_dependency_versions(
                    existing.version,
                    dep.version,
                ),
            )
        return list(merged.values())


class PluginDependencySchema(BaseModel):
    """Plugin dependency declaration / 插件依赖声明"""

    model_config = ConfigDict(extra="forbid")

    plugin: str
    version: str = "*"

    @field_validator("plugin")
    @classmethod
    def validate_plugin(cls, v: str) -> str:
        return validate_plugin_dependency_name(v)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        return validate_plugin_dependency_version(v)

    def to_requirement(self) -> PluginDependencyRequirement:
        return PluginDependencyRequirement(plugin=self.plugin, version=self.version)


class DeveloperSchema(BaseModel):
    """Developer information / 开发者信息"""

    name: str = ""
    email: str = ""
    url: str = ""


class TrialSchema(BaseModel):
    """Trial period configuration / 试用期配置"""

    enabled: bool = False
    days: int = 14


class PricingSchema(BaseModel):
    """Pricing information / 定价信息"""

    type: str = "free"
    price: float | None = None
    currency: str = "CNY"
    trial: TrialSchema = Field(default_factory=TrialSchema)


class ResourcesSchema(BaseModel):
    """Resources declaration / 资源声明"""

    readme: I18nText = Field(default_factory=dict)
    changelog: str = ""
    screenshots: list[str] = Field(default_factory=list)
    documentation_url: str = ""


# ============================================================
# Top-level PluginManifest / 顶层 PluginManifest
# ============================================================

_NAME_PATTERN = _PLUGIN_NAME_PATTERN
_VALID_SCOPES = {e.value for e in ResourceScopeEnum}

# Defined plugin capabilities whitelist (aligned with strings used in PluginContext._require())
# New capabilities must be added to this set
# / 已定义的插件能力白名单（与 PluginContext._require() 中使用的字符串对齐）
# 新增能力时需要同步更新此集合
_VALID_CAPABILITIES: frozenset[str] = frozenset({
    "db:read",           # Read database (own tables) / 读取数据库（自有表）
    "db:write",          # Write database (own tables) / 写入数据库（自有表）
    "db:own_tables",     # Operate own px_ tables (includes read+write) / 操作自有 px_ 数据表
    "platform:read",     # Read host snapshots via sandbox facade / 通过沙箱门面读取宿主快照
    "http:outbound",     # Send outbound HTTP requests (with SSRF protection) / 发送外部 HTTP 请求
    "storage:read",      # Read storage files / 读取存储文件
    "storage:write",     # Write storage files / 写入存储文件
    "ai:call",           # Call AI features (via SystemAgentAssignment) / 调用 AI 功能
    "config:write",      # Modify plugin's own config / 修改插件自身配置
    "notifications:send",# Send notifications / WebSocket push / 发送通知
})


class PluginManifest(BaseModel):
    """
    Plugin manifest top-level schema.
    / 插件清单顶层 Schema

    Corresponds to the complete structure of plugin.yaml.
    / 对应 plugin.yaml 文件的完整结构。
    """

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


DependenciesSchema.model_rebuild()
