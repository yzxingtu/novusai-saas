"""
AI 网关调用 API (Tenant) / AI Gateway API (Tenant)

提供企业端 AI 代理调用接口，支持配额和限流检查
Provides tenant AI proxy call endpoints with quota and rate limit checks
"""

from fastapi import Request

from app.ai.exceptions import AIGatewayError
from app.ai.internal_ai_service import InternalAIService
from app.ai.quota_exceptions import QuotaExceeded
from app.ai.rate_limiter import RateLimitExceeded
from app.ai.utils import parse_messages, parse_provider_and_model
from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import build_exception_debug, success
from app.enums import ErrorCode
from app.enums.rbac import PermissionScope
from app.exceptions import (
    BusinessException,
    ExternalServiceException,
    NotFoundException,
)
from app.rbac.decorators import (
    action_create,
    permission_resource,
)
from app.schemas.ai.gateway import (
    ChatRequest,
    EmbeddingRequest,
)
from app.services.ai.account_ai_access_service import AccountAIAccessService
from app.services.tenant.quota_service import QuotaService


async def _ensure_tenant_ai_gateway_access(
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
) -> None:
    """Fail closed before tenant-facing direct AI gateway calls."""
    await AccountAIAccessService(db).require_tenant_admin_ai_access(tenant_admin)
    api_check = await QuotaService.check_api_quota_for_tenant_id(
        db,
        tenant_admin.tenant_id,
    )
    if not api_check.allowed:
        raise BusinessException(
            message=api_check.message or _("quota.api_calls_exceeded"),
            code=ErrorCode.CONFLICT,
        )


@permission_resource(
    resource="ai_gateway",
    name="menu.tenant.ai_gateway",
    scope=PermissionScope.TENANT,
    parent_resource="ai_settings",
)
class TenantAIGatewayController(TenantController):
    """
    AI 网关控制器 (Tenant) / AI Gateway Controller (Tenant)

    企业端 AI 网关调用接口，支持配额和限流检查
    Tenant AI gateway call endpoints with quota and rate limit checks
    """

    prefix = "/ai/gateway"
    tags = [_("menu.tags.tenant_ai_gateway")]

    def _register_routes(self) -> None:
        router = self.router

        @router.post("/chat", summary="AI 聊天对话（非流式）")
        @action_create("action.ai_gateway.chat")
        async def chat(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            body: ChatRequest,
        ):
            """
            AI 聊天对话（非流式） / AI chat conversation (non-streaming)

            权限 / Permission: ai_gateway:chat
            """
            await _ensure_tenant_ai_gateway_access(db, tenant_admin)
            provider_code, model = parse_provider_and_model(body.model_code)
            messages = parse_messages(body.messages)

            tools = None
            if body.tools:
                tools = [tool.model_dump() for tool in body.tools]

            try:
                service = InternalAIService(db)
                response = await service.chat(
                    provider_code=provider_code,
                    messages=messages,
                    model=model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    top_p=body.top_p,
                    stream=False,
                    tools=tools,
                    tenant_id=tenant_admin.tenant_id,
                    user_id=tenant_admin.id,
                    user_type="tenant_admin",
                )
                return success(data=response.__dict__, message=_("common.success"))
            except (
                AIGatewayError,
                RateLimitExceeded,
                QuotaExceeded,
                NotFoundException,
                BusinessException,
            ):
                raise
            except Exception as e:
                raise ExternalServiceException(
                    message=_("ai.error.call_failed"),
                    debug=build_exception_debug(e),
                ) from e

        @router.post("/chat/stream", summary="AI 聊天对话（流式 SSE）")
        @action_create("action.ai_gateway.chat_stream")
        async def chat_stream(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            body: ChatRequest,
        ):
            """
            AI 聊天对话（流式 SSE） / AI chat conversation (streaming SSE)

            权限 / Permission: ai_gateway:chat_stream
            """
            await _ensure_tenant_ai_gateway_access(db, tenant_admin)
            provider_code, model = parse_provider_and_model(body.model_code)
            messages = parse_messages(body.messages)

            tools = None
            if body.tools:
                tools = [tool.model_dump() for tool in body.tools]

            try:
                service = InternalAIService(db)
                response = await service.stream_chat(
                    provider_code=provider_code,
                    messages=messages,
                    model=model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    top_p=body.top_p,
                    tools=tools,
                    tenant_id=tenant_admin.tenant_id,
                    user_id=tenant_admin.id,
                    user_type="tenant_admin",
                )
                return response
            except (
                AIGatewayError,
                RateLimitExceeded,
                QuotaExceeded,
                NotFoundException,
                BusinessException,
            ):
                raise
            except Exception as e:
                raise ExternalServiceException(
                    message=_("ai.error.call_failed"),
                    debug=build_exception_debug(e),
                ) from e

        @router.post("/embedding", summary="文本向量化")
        @action_create("action.ai_gateway.embedding")
        async def embedding(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            body: EmbeddingRequest,
        ):
            """
            文本向量化 / Text embedding

            权限 / Permission: ai_gateway:embedding
            """
            await _ensure_tenant_ai_gateway_access(db, tenant_admin)
            provider_code, model = parse_provider_and_model(body.model_code)

            try:
                service = InternalAIService(db)
                response = await service.embedding(
                    provider_code=provider_code,
                    texts=body.texts,
                    model=model,
                    tenant_id=tenant_admin.tenant_id,
                    user_id=tenant_admin.id,
                    user_type="tenant_admin",
                )
                return success(data=response.__dict__, message=_("common.success"))
            except (
                AIGatewayError,
                RateLimitExceeded,
                QuotaExceeded,
                NotFoundException,
                BusinessException,
            ):
                raise
            except Exception as e:
                raise ExternalServiceException(
                    message=_("ai.error.embedding_failed"),
                    debug=build_exception_debug(e),
                ) from e


# 导出路由器 / Export router
router = TenantAIGatewayController.get_router()

__all__ = ["router", "TenantAIGatewayController"]
