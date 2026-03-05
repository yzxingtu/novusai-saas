"""
控制器基类模块

提供 API 控制器层的基类，包括：
- BaseController: 通用控制器基类
- TenantController: 租户级控制器基类
- GlobalController: 全局控制器基类（平台管理端）

使用示例:
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
    控制器基类

    通过类方法定义路由，结合 @permission_resource 和 @permission_action 装饰器
    自动注册权限到数据库。
    """

    # 路由配置
    prefix: str = ""
    tags: list[str] = []
    dependencies: list = []

    # 关联的服务类
    service_class: type | None = None

    # 实例缓存（单例）
    _instance: "BaseController | None" = None
    _router: APIRouter | None = None

    def __new__(cls: type[T]) -> T:
        """单例模式，确保每个控制器类只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore

    @classmethod
    def get_router(cls) -> APIRouter:
        """
        获取控制器的路由器

        懒加载创建路由器并注册路由
        """
        if cls._router is None:
            cls._router = APIRouter(
                prefix=cls.prefix,
                tags=cls.tags,
                dependencies=cls.dependencies,
            )
            # 创建实例并注册路由
            instance = cls()
            instance._register_routes()

            # 将 resource 注入到操作方法（用于自动权限检查）
            cls._inject_resource_to_actions()

            # 自动扫描并注册操作权限
            from app.rbac.decorators import register_action_permissions
            register_action_permissions(cls, cls._router)
        return cls._router

    @classmethod
    def _inject_resource_to_actions(cls) -> None:
        """
        将 _permission_resource 注入到所有带权限装饰器的方法

        这样装饰器在运行时可以获取 resource 来构造完整的权限码
        """
        resource = getattr(cls, "_permission_resource", None)
        if not resource:
            return

        if not cls._router:
            return

        # 扫描路由器上的所有路由
        for route in cls._router.routes:
            endpoint = getattr(route, "endpoint", None)
            if not endpoint:
                continue

            # 如果有 _permission_action 属性，注入 resource
            if hasattr(endpoint, "_permission_action"):
                endpoint._permission_resource = resource  # type: ignore

    @property
    def router(self) -> APIRouter:
        """获取路由器实例"""
        return self.__class__.get_router()

    def _register_routes(self) -> None:
        """
        注册路由

        子类重写此方法来注册具体的路由处理函数
        """
        pass

    def get_service(self, db: Any) -> Any:
        """
        获取服务实例

        Args:
            db: 数据库会话

        Returns:
            服务实例
        """
        if self.service_class:
            return self.service_class(db)
        return None

    # ========================================
    # 钩子方法（子类可重写）
    # ========================================

    def before_request(self, request: Any) -> None:
        """
        请求前钩子

        可用于：日志记录、权限预检等

        Args:
            request: 请求对象
        """
        pass

    def after_request(self, response: Any) -> Any:
        """
        请求后钩子

        可用于：响应处理、日志记录等

        Args:
            response: 响应对象

        Returns:
            处理后的响应
        """
        return response


class TenantController(BaseController):
    """
    租户级控制器基类

    用于租户管理后台 API，自动注入租户上下文
    """

    _instance: "TenantController | None" = None
    _router: APIRouter | None = None

    def get_service(self, db: Any, tenant_id: int) -> Any:
        """
        获取租户级服务实例

        Args:
            db: 数据库会话
            tenant_id: 租户 ID

        Returns:
            租户服务实例
        """
        if self.service_class:
            return self.service_class(db, tenant_id)
        return None


class GlobalController(BaseController):
    """
    全局控制器基类

    用于平台管理后台 API，超管或系统级操作，无租户隔离
    """

    _instance: "GlobalController | None" = None
    _router: APIRouter | None = None


# 导出
__all__ = ["BaseController", "TenantController", "GlobalController"]
