"""
Tenant Identification Middleware / 企业识别中间件

Resolves tenant info from request Host header, supports / 根据 Host 头解析企业信息，支持：
1. Subdomain mode / 子域名模式: {tenant_code}.app.novusai.com
2. Custom domain mode / 自定义域名模式: custom.domain.com -> tenant_domains table
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models import Tenant, TenantDomain

logger = get_logger(__name__)


class TenantContext:
    """
    Tenant Context.
    企业上下文。

    Stores tenant info resolved from request / 存储从请求中解析出的企业信息
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
        """Whether tenant is resolved / 企业是否已解析"""
        return self.tenant is not None

    def __repr__(self) -> str:
        return f"<TenantContext(tenant_id={self.tenant_id}, code={self.tenant_code}, type={self.domain_type})>"


def parse_tenant_from_host(host: str) -> tuple[str | None, str]:
    """
    Parse tenant info from Host header / 从 Host 头解析企业信息

    Args:
        host: Request Host header / 请求的 Host 头, e.g. "abc.app.novusai.com" or "custom.com"

    Returns:
        tuple: (tenant_code, domain_type)
        - Subdomain / 子域名: (tenant_code, "subdomain")
        - Custom domain / 自定义域名: (None, "custom")
        - Unresolvable / 无法解析: (None, "unknown")
    """
    if not host:
        return None, "unknown"

    # Remove port number / 移除端口号
    host = host.split(":")[0].lower()

    # Check if subdomain mode / 检查是否是子域名模式
    suffix = settings.TENANT_DOMAIN_SUFFIX.lower()
    if host.endswith(suffix):
        # Extract subdomain part / 提取子域名部分
        subdomain = host[:-len(suffix)]
        if subdomain and "." not in subdomain:
            # Valid tenant subdomain (no dots) / 合法的企业子域名
            return subdomain, "subdomain"

    # Possibly custom domain / 可能是自定义域名
    # Exclude platform main domain / 排除平台主域名
    if host == suffix.lstrip("."):
        return None, "unknown"

    # Exclude configured platform admin domains to avoid unnecessary DB queries / 排除管理端域名
    platform_domains = [d.lower() for d in settings.platform_domains_list]
    if host in platform_domains:
        return None, "unknown"

    return None, "custom"


class TenantMiddleware:
    """
    Tenant Identification Middleware (pure ASGI implementation). / 企业识别中间件（纯 ASGI 实现）。

    Resolves tenant info in each request and stores to request.state.tenant_ctx.
    在每个请求中解析企业信息并存储到 request.state.tenant_ctx。
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    # Path prefixes that need tenant domain resolution / 需要执行企业域名解析的路径前缀
    # Note: No /api/v1/ routes in this project (API routes use /admin/, /tenant/, /api/user/, /api/public/)
    TENANT_PATHS = (
        "/tenant/",
        "/api/user/",
        "/api/public/tenant",
    )

    @staticmethod
    def _needs_tenant_resolution(path: str) -> bool:
        """Check if request path needs tenant domain resolution / 判断请求路径是否需要企业域名解析"""
        return any(path.startswith(prefix) for prefix in TenantMiddleware.TENANT_PATHS)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Get request path / 获取请求路径
        path = scope.get("path", "")

        # Non-tenant paths skip domain resolution, set empty context to avoid downstream errors / 非企业路径跳过解析
        if not self._needs_tenant_resolution(path):
            if "state" not in scope:
                scope["state"] = {}
            scope["state"]["tenant_ctx"] = TenantContext()
            await self.app(scope, receive, send)
            return

        # Get Host header / 获取 Host 头
        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"").decode("utf-8", errors="ignore")

        # Parse tenant / 解析企业
        tenant_code, domain_type = parse_tenant_from_host(host)

        # Create tenant context / 创建企业上下文
        tenant_ctx = TenantContext(
            tenant_code=tenant_code,
            domain_type=domain_type,
        )

        # If tenant info resolved, load from DB / 如果解析出了企业信息，从数据库加载
        if tenant_code or domain_type == "custom":
            async with async_session_factory() as db:
                tenant = await self._resolve_tenant(db, tenant_code, host, domain_type)
                if tenant:
                    tenant_ctx.tenant = tenant
                    tenant_ctx.tenant_id = tenant.id
                    tenant_ctx.tenant_code = tenant.code

        # Store tenant context in scope state / 将企业上下文存储到 scope state
        # FastAPI maps this to request.state / FastAPI 会将其映射到 request.state
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
        Resolve tenant from database / 从数据库解析企业

        Args:
            db: Database session / 数据库会话
            tenant_code: Tenant code (subdomain mode) / 企业代码
            host: Original Host (custom domain mode) / 原始 Host
            domain_type: Domain type / 域名类型

        Returns:
            Tenant or None
        """
        if domain_type == "subdomain" and tenant_code:
            # Subdomain mode: query by code directly / 子域名模式：直接按 code 查询
            result = await db.execute(
                select(Tenant).where(
                    Tenant.code == tenant_code,
                    Tenant.is_active.is_(True),
                    Tenant.is_deleted.is_(False),
                )
            )
            return result.scalar_one_or_none()

        elif domain_type == "custom":
            # Custom domain mode: query tenant_domains table / 自定义域名模式
            # Remove port number / 移除端口号
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
                # Check if tenant is active / 检查企业是否激活
                return tenant_domain.tenant

        return None


def get_tenant_context(request: Request) -> TenantContext | None:
    """
    Get tenant context from request / 从请求中获取企业上下文

    Usage:
        tenant_ctx = get_tenant_context(request)
        if tenant_ctx and tenant_ctx.is_resolved:
            logger.debug("Tenant: {}", tenant_ctx.tenant.name)
    """
    return getattr(request.state, "tenant_ctx", None)


def get_current_tenant(request: Request) -> Tenant | None:
    """
    Get current tenant from request / 从请求中获取当前企业

    Usage:
        tenant = get_current_tenant(request)
        if tenant:
            logger.debug("Tenant: {}", tenant.name)
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
