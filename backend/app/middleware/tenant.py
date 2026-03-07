"""
租户识别中间件

根据请求的 Host 头解析租户信息，支持：
1. 子域名模式: {tenant_code}.app.novusai.com
2. 自定义域名模式: custom.domain.com -> 查询 tenant_domains 表
"""


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.database import async_session_factory
from app.models import Tenant, TenantDomain


class TenantContext:
    """
    租户上下文

    存储从请求中解析出的租户信息
    """

    def __init__(
        self,
        tenant_id: int | None = None,
        tenant_code: str | None = None,
        tenant: Tenant | None = None,
        domain_type: str = "unknown",  # subdomain, custom, unknown
    ):
        self.tenant_id = tenant_id
        self.tenant_code = tenant_code
        self.tenant = tenant
        self.domain_type = domain_type

    @property
    def is_resolved(self) -> bool:
        """租户是否已解析"""
        return self.tenant is not None

    def __repr__(self) -> str:
        return f"<TenantContext(tenant_id={self.tenant_id}, code={self.tenant_code}, type={self.domain_type})>"


def parse_tenant_from_host(host: str) -> tuple[str | None, str]:
    """
    从 Host 头解析租户信息

    Args:
        host: 请求的 Host 头，如 "abc.app.novusai.com" 或 "custom.com"

    Returns:
        tuple: (tenant_code, domain_type)
        - 如果是子域名，返回 (tenant_code, "subdomain")
        - 如果是自定义域名，返回 (None, "custom")
        - 如果无法解析，返回 (None, "unknown")
    """
    if not host:
        return None, "unknown"

    # 移除端口号
    host = host.split(":")[0].lower()

    # 检查是否是子域名模式
    suffix = settings.TENANT_DOMAIN_SUFFIX.lower()
    if host.endswith(suffix):
        # 提取子域名部分
        subdomain = host[:-len(suffix)]
        if subdomain and "." not in subdomain:
            # 合法的租户子域名（不含点号）
            return subdomain, "subdomain"

    # 可能是自定义域名
    # 排除平台主域名（如 app.novusai.com 本身）
    if host == suffix.lstrip("."):
        return None, "unknown"

    # 排除已配置的平台管理端域名，避免不必要的 DB 查询
    platform_domains = [d.lower() for d in settings.platform_domains_list]
    if host in platform_domains:
        return None, "unknown"

    return None, "custom"


class TenantMiddleware:
    """
    租户识别中间件（纯 ASGI 实现）

    在每个请求中解析租户信息并存储到 request.state.tenant_ctx
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    # 需要执行租户域名解析的路径前缀
    TENANT_PATHS = (
        "/tenant/",
        "/api/v1/",
        "/api/user/",
        "/api/public/tenant",
    )

    @staticmethod
    def _needs_tenant_resolution(path: str) -> bool:
        """判断请求路径是否需要执行租户域名解析"""
        return any(path.startswith(prefix) for prefix in TenantMiddleware.TENANT_PATHS)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # 获取请求路径
        path = scope.get("path", "")

        # 非租户路径跳过域名解析，设置空上下文避免下游报错
        if not self._needs_tenant_resolution(path):
            if "state" not in scope:
                scope["state"] = {}
            scope["state"]["tenant_ctx"] = TenantContext()
            await self.app(scope, receive, send)
            return

        # 获取 Host 头
        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"").decode("utf-8", errors="ignore")

        # 解析租户
        tenant_code, domain_type = parse_tenant_from_host(host)

        # 创建租户上下文
        tenant_ctx = TenantContext(
            tenant_code=tenant_code,
            domain_type=domain_type,
        )

        # 如果解析出了租户信息，从数据库加载
        if tenant_code or domain_type == "custom":
            async with async_session_factory() as db:
                tenant = await self._resolve_tenant(db, tenant_code, host, domain_type)
                if tenant:
                    tenant_ctx.tenant = tenant
                    tenant_ctx.tenant_id = tenant.id
                    tenant_ctx.tenant_code = tenant.code

        # 将租户上下文存储到 scope 的 state 中
        # FastAPI 会将其映射到 request.state
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["tenant_ctx"] = tenant_ctx

        await self.app(scope, receive, send)

    async def _resolve_tenant(
        self,
        db: AsyncSession,
        tenant_code: str | None,
        host: str,
        domain_type: str,
    ) -> Tenant | None:
        """
        从数据库解析租户

        Args:
            db: 数据库会话
            tenant_code: 租户代码（子域名模式）
            host: 原始 Host（自定义域名模式）
            domain_type: 域名类型

        Returns:
            Tenant or None
        """
        if domain_type == "subdomain" and tenant_code:
            # 子域名模式：直接按 code 查询
            result = await db.execute(
                select(Tenant).where(
                    Tenant.code == tenant_code,
                    Tenant.is_active.is_(True),
                    Tenant.is_deleted.is_(False),
                )
            )
            return result.scalar_one_or_none()

        elif domain_type == "custom":
            # 自定义域名模式：查询 tenant_domains 表
            # 移除端口号
            domain = host.split(":")[0].lower()

            result = await db.execute(
                select(TenantDomain)
                .options(selectinload(TenantDomain.tenant))
                .where(
                    TenantDomain.domain == domain,
                    TenantDomain.is_verified.is_(True),
                    TenantDomain.is_deleted.is_(False),
                )
            )
            tenant_domain = result.scalar_one_or_none()

            if (
                tenant_domain
                and tenant_domain.tenant
                and tenant_domain.tenant.is_active
                and not tenant_domain.tenant.is_deleted
            ):
                # 检查租户是否激活
                return tenant_domain.tenant

        return None


def get_tenant_context(request: Request) -> TenantContext | None:
    """
    从请求中获取租户上下文

    Usage:
        tenant_ctx = get_tenant_context(request)
        if tenant_ctx and tenant_ctx.is_resolved:
            print(f"Tenant: {tenant_ctx.tenant.name}")
    """
    return getattr(request.state, "tenant_ctx", None)


def get_current_tenant(request: Request) -> Tenant | None:
    """
    从请求中获取当前租户

    Usage:
        tenant = get_current_tenant(request)
        if tenant:
            print(f"Tenant: {tenant.name}")
    """
    ctx = get_tenant_context(request)
    if ctx and ctx.is_resolved:
        return ctx.tenant
    return None


__all__ = [
    "TenantMiddleware",
    "TenantContext",
    "get_tenant_context",
    "get_current_tenant",
    "parse_tenant_from_host",
]
