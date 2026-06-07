"""
Tenant Identification Middleware / 企业识别中间件

Resolves tenant info from request Host header, supports / 根据 Host 头解析企业信息，支持：
1. Subdomain mode / 子域名模式: {tenant_code}.app.novusai.com
2. Custom domain mode / 自定义域名模式: custom.domain.com -> tenant_domains table
"""

from urllib.parse import urlparse

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
        domain_type: str = "unknown",  # subdomain, custom, unknown / 域名类型：子域名、自定义、未知
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
        subdomain = host[: -len(suffix)]
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
        "/api/public/captcha",
        "/plugin-public-assets/tenant/",
        "/plugin-public-assets/user/",
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

        # Parse tenant from Host (primary) / 优先用 Host 头解析企业
        tenant_code, domain_type = parse_tenant_from_host(host)

        # 预解析 Origin（用于跨域兜底） / Pre-parse Origin for cross-origin fallback
        # 跨域场景：租户前端（如 https://t3tetj7r5.nvuai.online）调用集中式 API
        # 域名（如 https://apidemo.nvuai.cc），此时 Host 头无法识别租户身份，
        # 必须从 Origin 头还原真实租户。
        # Cross-origin scenario: tenant frontend on https://t3tetj7r5.nvuai.online
        # calls a centralised API domain like https://apidemo.nvuai.cc, in which
        # case the Host header cannot identify the tenant and we must recover the
        # real tenant from the Origin header.
        origin_host: str | None = None
        origin_code: str | None = None
        origin_type: str = "unknown"
        origin_raw = headers.get(b"origin", b"").decode("utf-8", errors="ignore")
        if origin_raw:
            try:
                parsed = urlparse(origin_raw)
                origin_host = (parsed.hostname or "").lower() or None
            except ValueError:
                origin_host = None
            if origin_host and origin_host != host.split(":")[0].lower():
                origin_code, origin_type = parse_tenant_from_host(origin_host)
            else:
                # Origin 与 Host 同域则无回退价值 / Same-origin: no fallback value
                origin_host = None

        # 创建企业上下文（占位） / Create tenant context placeholder
        tenant_ctx = TenantContext(
            tenant_code=tenant_code,
            domain_type=domain_type,
        )

        # 两阶段查询：Host 优先 → Origin 兜底重试。
        # Two-stage lookup: Host first, fallback to Origin when Host fails.
        # 这样能同时覆盖：
        # 1. 正常 subdomain / custom 域名（一阶段命中）
        # 2. 集中式 API 跨域调用（Host 是 API 代理域名、不在 DB 中），
        #    无论 Host 被解析为 subdomain / custom / unknown 都能由 Origin 兜底
        async with async_session_factory() as db:
            tenant = None
            # Stage 1: Host
            if tenant_code or domain_type == "custom":
                tenant = await self._resolve_tenant(
                    db, tenant_code, host, domain_type
                )
            # Stage 2: Origin fallback when Host lookup failed
            # 当 Host 查不到租户、且 Origin 能解析出候选租户时重试。
            if (
                tenant is None
                and origin_host
                and (origin_code or origin_type == "custom")
            ):
                tenant = await self._resolve_tenant(
                    db, origin_code, origin_host, origin_type
                )
                if tenant is not None:
                    tenant_code, domain_type = origin_code, origin_type

            if tenant is not None:
                tenant_ctx.tenant = tenant
                tenant_ctx.tenant_id = tenant.id
                tenant_ctx.tenant_code = tenant.code
                tenant_ctx.domain_type = domain_type

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
                # 中文: 运行时域名解析只负责企业身份识别；套餐自定义域名权益由新增、SSL、续期等写侧流程校验。
                # EN: Runtime domain resolution only identifies the tenant; create/SSL/renewal flows enforce custom-domain entitlements.
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
