"""
权限装饰器

通过装饰器在控制器上声明式定义权限，应用启动时自动扫描并同步到数据库

新版本支持单一声明原则：装饰器同时负责「权限注册」和「权限检查」，消除重复声明
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, TypeVar

from fastapi import HTTPException, Request, status

from app.core.i18n import _
from app.enums.rbac import PermissionScope, PermissionType

F = TypeVar("F", bound=Callable[..., Any])


# ==================== 访问控制标记 ====================
# 用于标记端点的访问级别

# 公开访问（无需认证）
ACCESS_PUBLIC = "__access_public__"
# 仅需认证（无需权限检查）
ACCESS_AUTH_ONLY = "__access_auth_only__"
# 需要权限检查（默认，由 @permission_action 标记）
ACCESS_PERMISSION = "__access_permission__"


def public(func: F) -> F:
    """
    公开访问装饰器

    标记端点为公开访问，无需认证和权限检查。

    适用场景：
    - 登录接口
    - Token 刷新接口
    - 健康检查
    - 公开资源

    Example:
        @router.post("/login")
        @public
        async def login(data: LoginRequest):
            ...
    """
    func._access_level = ACCESS_PUBLIC  # type: ignore
    return func


def auth_only(func: F) -> F:
    """
    仅需认证装饰器

    标记端点只需要登录认证，无需额外的权限检查。

    适用场景：
    - 获取当前用户信息
    - 获取当前用户菜单
    - 修改当前用户密码
    - 用户登出

    Example:
        @router.get("/me")
        @auth_only
        async def get_me(current_admin: ActiveAdmin):
            ...
    """
    func._access_level = ACCESS_AUTH_ONLY  # type: ignore
    return func


@dataclass
class MenuConfig:
    """
    菜单配置

    Attributes:
        icon: 菜单图标，使用 Lucide 图标库 (https://lucide.dev/icons)
              格式: "lucide:{icon-name}"，如 "lucide:settings", "lucide:users"
              图标名称使用 kebab-case（小写字母，单词间用连字符分隔）
        path: 菜单路由路径
        component: 前端组件路径
        parent: 父菜单资源标识
        sort_order: 排序权重，数值越小越靠前
        hidden: 是否隐藏菜单（仅做权限控制，不在菜单中显示）
    """

    icon: str | None = None
    path: str | None = None
    component: str | None = None
    parent: str | None = None  # 父菜单资源标识
    sort_order: int = 0
    hidden: bool = False  # 是否隐藏菜单（仅做权限控制）


@dataclass
class PermissionMeta:
    """权限元信息"""

    code: str
    name: str
    type: PermissionType
    scope: PermissionScope
    resource: str
    action: str
    description: str = ""
    # 菜单专用
    icon: str | None = None
    path: str | None = None
    component: str | None = None
    parent_code: str | None = None
    sort_order: int = 0
    hidden: bool = False


def permission_resource(
    resource: str,
    name: str,
    scope: PermissionScope = PermissionScope.ALL_TENANTS,
    menu: MenuConfig | None = None,
    description: str = "",
    parent_resource: str | None = None,
) -> Callable[[type], type]:
    """
    资源权限装饰器（用于控制器类）

    自动注册：
    1. 菜单权限（如果提供了 menu 配置）
    2. 操作权限（通过 @action_* 装饰器自动扫描）

    Args:
        resource: 资源标识，如 "user", "order"
        name: 资源名称，如 "用户管理"
        scope: 权限作用域
        menu: 菜单配置（可选）
        description: 描述
        parent_resource: 父资源标识，用于将操作权限挂载到指定资源的菜单下（适用于无菜单的资源）

    Example:
        @permission_resource(
            resource="user",
            name="用户管理",
            scope=PermissionScope.ALL_TENANTS,
            menu=MenuConfig(icon="user", path="/users", component="user/List")
        )
        class UserController:
            # 操作权限通过 @action_read 等装饰器自动注册
            @action_read("查看用户")
            async def list_users(self, ...):
                ...

        # 无菜单的资源，操作权限挂载到父资源下
        @permission_resource(
            resource="tenant_domain",
            name="租户域名管理",
            scope=PermissionScope.ADMIN_ONLY,
            parent_resource="tenant",  # 操作权限挂载到 tenant 菜单下
        )
        class TenantDomainController:
            ...
    """
    # 延迟导入避免循环引用
    from app.rbac.registry import permission_registry

    def decorator(cls: type) -> type:
        # 保存资源元信息到类属性
        cls._permission_resource = resource  # type: ignore
        cls._permission_name = name  # type: ignore
        cls._permission_scope = scope  # type: ignore
        cls._permission_parent_resource = parent_resource  # type: ignore

        # 注册菜单权限
        if menu:
            scope_prefix = "admin" if scope == PermissionScope.ADMIN_ONLY else "tenant"
            menu_code = f"menu:{scope_prefix}.{resource}"
            parent_code = None
            if menu.parent:
                parent_code = f"menu:{scope_prefix}.{menu.parent}"

            menu_perm = PermissionMeta(
                code=menu_code,
                name=name,
                type=PermissionType.MENU,
                scope=scope,
                resource="menu",
                action=f"{scope_prefix}.{resource}",
                description=description,
                icon=menu.icon,
                path=menu.path,
                component=menu.component,
                parent_code=parent_code,
                sort_order=menu.sort_order,
                hidden=menu.hidden,
            )
            permission_registry.register(menu_perm)

        return cls

    return decorator


def permission_action(
    action: str,
    name: str,
    description: str = "",
    auto_check: bool = True,
) -> Callable[[F], F]:
    """
    操作权限装饰器（用于控制器方法）

    功能：
    1. 注册操作权限到 registry（应用启动时同步到数据库）
    2. 运行时自动检查权限（通过 request.state 获取用户权限）

    权限码自动推导规则：
    - 从所属类的 _permission_resource 获取 resource
    - 最终权限码 = f"{resource}:{action}"

    Args:
        action: 操作标识，如 "create", "list", "detail", "update", "delete"
        name: 操作名称（i18n key），如 "action.user.list"
        description: 描述
        auto_check: 是否自动检查权限（默认 True）

    Example:
        @permission_action("list", "action.user.list")
        async def list_users(...):
            ...
    """
    def decorator(func: F) -> F:
        # 保存操作元信息到函数属性（用于权限注册）
        func._permission_action = {  # type: ignore
            "action": action,
            "name": name,
            "description": description,
            "auto_check": auto_check,
        }

        # 标记需要的权限（用于依赖注入检查）
        func._required_permission_action = action  # type: ignore

        # 标记访问级别为需要权限检查
        func._access_level = ACCESS_PERMISSION  # type: ignore

        if not auto_check:
            return func

        # 包装函数，添加自动权限检查
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 从 kwargs 中获取 request 对象
            request: Request | None = kwargs.get("request")

            # 如果 kwargs 中没有，尝试从 args 中查找
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            # 获取权限码（resource 由 base_controller 注入）
            resource = getattr(wrapper, "_permission_resource", None)

            if resource and request:
                permission_code = f"{resource}:{action}"

                # 从 request.state 获取用户权限信息
                user_permissions: set[str] = getattr(request.state, "user_permissions", set())

                # 检查权限
                has_permission = _check_permission(user_permissions, permission_code)

                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=_("rbac.permission_denied"),
                    )

            return await func(*args, **kwargs)

        # 复制原始函数的属性到 wrapper
        wrapper._permission_action = func._permission_action  # type: ignore
        wrapper._required_permission_action = func._required_permission_action  # type: ignore
        wrapper._access_level = ACCESS_PERMISSION  # type: ignore

        return wrapper  # type: ignore

    return decorator


def _check_permission(user_perms: set[str], required: str) -> bool:
    """
    检查用户是否拥有指定权限

    支持：
    - 精确匹配: admin_user:list
    - 通配符: * (所有权限)
    - 资源通配符: admin_user:* (某资源的所有操作)
    """
    if "*" in user_perms:
        return True
    if required in user_perms:
        return True
    if ":" in required:
        resource = required.split(":")[0]
        if f"{resource}:*" in user_perms:
            return True
    return False


# ==================== 快捷装饰器 ====================

def _extract_action_from_name(name: str, default_action: str) -> str:
    """
    从 i18n name 中提取细粒度 action

    例如: "action.admin.list" -> "list"
          "action.role.detail" -> "detail"
          "查看列表" -> default_action
    """
    if name.startswith("action.") and name.count(".") >= 2:
        # 格式: action.{resource}.{action}
        return name.split(".")[-1]
    return default_action


def action_read(name: str = "查看", **kwargs: Any) -> Callable[[F], F]:
    """
    查看权限快捷装饰器

    支持细粒度权限：
    - @action_read("action.user.list") -> 权限 code: user:list
    - @action_read("action.user.detail") -> 权限 code: user:detail
    - @action_read("查看") -> 权限 code: user:read
    """
    action = _extract_action_from_name(name, "read")
    return permission_action(action, name, **kwargs)


def action_create(name: str = "创建", **kwargs: Any) -> Callable[[F], F]:
    """创建权限快捷装饰器"""
    action = _extract_action_from_name(name, "create")
    return permission_action(action, name, **kwargs)


def action_update(name: str = "编辑", **kwargs: Any) -> Callable[[F], F]:
    """编辑权限快捷装饰器"""
    action = _extract_action_from_name(name, "update")
    return permission_action(action, name, **kwargs)


def action_delete(name: str = "删除", **kwargs: Any) -> Callable[[F], F]:
    """删除权限快捷装饰器"""
    action = _extract_action_from_name(name, "delete")
    return permission_action(action, name, **kwargs)


def action_export(name: str = "导出", **kwargs: Any) -> Callable[[F], F]:
    """导出权限快捷装饰器"""
    action = _extract_action_from_name(name, "export")
    return permission_action(action, name, **kwargs)


def action_import(name: str = "导入", **kwargs: Any) -> Callable[[F], F]:
    """导入权限快捷装饰器"""
    action = _extract_action_from_name(name, "import")
    return permission_action(action, name, **kwargs)


# ==================== 操作权限自动注册 ====================

def register_action_permissions(controller_cls: type, router: Any) -> None:
    """
    扫描路由器上的路由，自动注册操作权限

    在控制器的 _register_routes 执行后调用，扫描路由器上所有带有
    _permission_action 属性的路由处理函数，并注册到 permission_registry。

    Args:
        controller_cls: 控制器类（带有 _permission_resource 等属性）
        router: FastAPI APIRouter 实例
    """
    from app.rbac.registry import permission_registry

    # 获取控制器的资源信息
    resource = getattr(controller_cls, "_permission_resource", None)
    scope = getattr(controller_cls, "_permission_scope", None)
    parent_resource = getattr(controller_cls, "_permission_parent_resource", None)

    if not resource or not scope:
        return

    # 构造父菜单权限 code（操作权限挂载到对应菜单下）
    from app.enums.rbac import PermissionScope
    scope_prefix = "admin" if scope == PermissionScope.ADMIN_ONLY else "tenant"

    # 优先使用 parent_resource 指定的父菜单，否则使用自己的资源菜单
    if parent_resource:
        parent_menu_code = f"menu:{scope_prefix}.{parent_resource}"
    else:
        parent_menu_code = f"menu:{scope_prefix}.{resource}"

    # 检查父菜单是否存在（不存在则不设置 parent_code）
    parent_code = parent_menu_code if parent_menu_code in permission_registry else None

    # 已注册的操作（避免重复）
    registered_actions: set[str] = set()

    # 扫描路由器上的所有路由
    for route in router.routes:
        # 获取路由的 endpoint 函数
        endpoint = getattr(route, "endpoint", None)
        if not endpoint:
            continue

        # 检查是否有 _permission_action 属性
        action_info = getattr(endpoint, "_permission_action", None)
        if not action_info:
            continue

        action = action_info["action"]

        # 避免重复注册
        if action in registered_actions:
            continue
        registered_actions.add(action)

        # 注册操作权限（挂载到对应菜单下）
        action_perm = PermissionMeta(
            code=f"{resource}:{action}",
            name=action_info["name"],
            type=PermissionType.OPERATION,
            scope=scope,
            resource=resource,
            action=action,
            description=action_info.get("description", ""),
            parent_code=parent_code,
        )
        permission_registry.register(action_perm)


__all__ = [
    # 访问控制标记
    "ACCESS_PUBLIC",
    "ACCESS_AUTH_ONLY",
    "ACCESS_PERMISSION",
    # 访问控制装饰器
    "public",
    "auth_only",
    # 权限装饰器
    "MenuConfig",
    "PermissionMeta",
    "permission_resource",
    "permission_action",
    "action_read",
    "action_create",
    "action_update",
    "action_delete",
    "action_export",
    "action_import",
    # 用于手动注册操作权限
    "register_action_permissions",
]
