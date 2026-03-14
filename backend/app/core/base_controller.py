"""
控制器基类模块 / Controller Base Module

提供 API 控制器层的基类，包括：
Provides base classes for the API controller layer, including:
- BaseController: 通用控制器基类 / Generic controller base class
- TenantController: 企业级控制器基类 / Tenant-scoped controller base class
- GlobalController: 全局控制器基类（平台管理端） / Global controller base class (platform admin)

使用示例 / Usage example:
    @permission_resource(
        resource="user",
        name="用户管理",
        scope=PermissionScope.ALL_TENANTS,
        menu=MenuConfig(icon="user", path="/users", component="user/List")
    )
    class UserController(TenantController):
        prefix = "/users"
        tags = ["用户管理"]

        @action_read("查看用户列表")
        async def list_users(self, db: DbSession, current_user: ActiveTenantAdmin):
            ...
"""

from typing import Any, TypeVar

from fastapi import APIRouter

T = TypeVar("T", bound="BaseController")


class BaseController:
    """
    控制器基类 / Controller Base Class

    通过类方法定义路由，结合 @permission_resource 和 @permission_action 装饰器
    自动注册权限到数据库。
    Defines routes via class methods, combined with @permission_resource and
    @permission_action decorators to automatically register permissions to the database.
    """

    # 路由配置 / Route configuration
    prefix: str = ""
    tags: list[str] = []
    dependencies: list = []

    # 关联的服务类 / Associated service class
    service_class: type | None = None

    # 实例缓存（单例） / Instance cache (singleton)
    _instance: "BaseController | None" = None
    _router: APIRouter | None = None

    def __new__(cls: type[T]) -> T:
        """单例模式，确保每个控制器类只有一个实例 / Singleton pattern, ensures one instance per controller class"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore

    @classmethod
    def get_router(cls) -> APIRouter:
        """
        获取控制器的路由器 / Get the controller's router

        懒加载创建路由器并注册路由
        Lazily creates the router and registers routes.
        """
        if cls._router is None:
            cls._router = APIRouter(
                prefix=cls.prefix,
                tags=cls.tags,
                dependencies=cls.dependencies,
            )
            # 创建实例并注册路由 / Create instance and register routes
            instance = cls()
            instance._register_routes()

            # 将 resource 注入到操作方法（用于自动权限检查） / Inject resource into action methods (for auto permission checks)
            cls._inject_resource_to_actions()

            # 自动扫描并注册操作权限 / Auto-scan and register action permissions
            from app.rbac.decorators import register_action_permissions
            register_action_permissions(cls, cls._router)
        return cls._router

    @classmethod
    def _inject_resource_to_actions(cls) -> None:
        """
        将 _permission_resource 注入到所有带权限装饰器的方法
        Inject _permission_resource into all methods decorated with permission decorators.

        这样装饰器在运行时可以获取 resource 来构造完整的权限码
        This allows decorators to get the resource at runtime to construct the full permission code.
        """
        resource = getattr(cls, "_permission_resource", None)
        if not resource:
            return

        if not cls._router:
            return

        # 扫描路由器上的所有路由 / Scan all routes on the router
        for route in cls._router.routes:
            endpoint = getattr(route, "endpoint", None)
            if not endpoint:
                continue

            # 如果有 _permission_action 属性，注入 resource / If has _permission_action attr, inject resource
            if hasattr(endpoint, "_permission_action"):
                endpoint._permission_resource = resource  # type: ignore

    @property
    def router(self) -> APIRouter:
        """获取路由器实例 / Get router instance"""
        return self.__class__.get_router()

    def _register_routes(self) -> None:
        """
        注册路由 / Register routes

        子类重写此方法来注册具体的路由处理函数
        Subclasses override this method to register specific route handlers.
        """
        pass

    def get_service(self, db: Any) -> Any:
        """
        获取服务实例 / Get service instance

        Args:
            db: 数据库会话 / Database session

        Returns:
            服务实例 / Service instance
        """
        if self.service_class:
            return self.service_class(db)
        return None

    # ========================================
    # 钩子方法（子类可重写） / Hook methods (overridable by subclasses)
    # ========================================

    def before_request(self, request: Any) -> None:
        """
        请求前钩子 / Pre-request hook

        可用于：日志记录、权限预检等
        Useful for: logging, permission pre-checks, etc.

        Args:
            request: 请求对象 / Request object
        """
        pass

    def after_request(self, response: Any) -> Any:
        """
        请求后钩子 / Post-request hook

        可用于：响应处理、日志记录等
        Useful for: response processing, logging, etc.

        Args:
            response: 响应对象 / Response object

        Returns:
            处理后的响应 / Processed response
        """
        return response


class TenantController(BaseController):
    """
    企业级控制器基类 / Tenant Controller Base Class

    用于企业管理后台 API，自动注入企业上下文
    Used for tenant admin APIs, automatically injects tenant context.
    """

    _instance: "TenantController | None" = None
    _router: APIRouter | None = None

    def get_service(self, db: Any, tenant_id: int) -> Any:
        """
        获取企业级服务实例 / Get tenant-scoped service instance

        Args:
            db: 数据库会话 / Database session
            tenant_id: 企业 ID / Tenant ID

        Returns:
            企业服务实例 / Tenant service instance
        """
        if self.service_class:
            return self.service_class(db, tenant_id)
        return None


class GlobalController(BaseController):
    """
    全局控制器基类 / Global Controller Base Class

    用于平台管理后台 API，超管或系统级操作，无企业隔离
    Used for platform admin APIs, super-admin or system-level operations, no tenant isolation.
    """

    _instance: "GlobalController | None" = None
    _router: APIRouter | None = None


# 导出 / Exports
__all__ = ["BaseController", "TenantController", "GlobalController"]
