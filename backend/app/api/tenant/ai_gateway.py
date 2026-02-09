"""
AI 网关调用 API (Tenant)

提供租户端 AI 代理调用接口，支持配额和限流检查
"""

from fastapi import Request

from app.ai.gateway import AIGateway
from app.ai.utils import parse_provider_and_model, parse_messages
from app.core.base_controller import TenantController
from app.core.deps import DbSession, ActiveTenantAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.rbac import PermissionScope
from app.exceptions import ExternalServiceException, BusinessException
from app.rbac.decorators import (
    permission_resource,
    action_create,
)
from app.schemas.ai.gateway import (
    ChatRequest,
    EmbeddingRequest,
)


@permission_resource(
    resource="ai_gateway",
    name="menu.tenant.ai_gateway",
    scope=PermissionScope.TENANT,
)
class TenantAIGatewayController(TenantController):
    """
    AI 网关控制器 (Tenant)

    租户端 AI 网关调用接口，支持配额和限流检查
    """

    prefix = "/ai/gateway"
    tags = ["AI 网关"]

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
            AI 聊天对话（非流式）

            权限: ai_gateway:chat
            """
            provider_code, model = parse_provider_and_model(body.model_code)
            messages = parse_messages(body.messages)

            tools = None
            if body.tools:
                tools = [tool.model_dump() for tool in body.tools]

            try:
                gateway = AIGateway(db)
                response = await gateway.chat(
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
                )
                return success(data=response.__dict__, message=_("common.success"))
            except Exception as e:
                raise ExternalServiceException(message=_("ai.error.call_failed") + f": {str(e)}")

        @router.post("/chat/stream", summary="AI 聊天对话（流式 SSE）")
        @action_create("action.ai_gateway.chat_stream")
        async def chat_stream(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            body: ChatRequest,
        ):
            """
            AI 聊天对话（流式 SSE）

            权限: ai_gateway:chat_stream
            """
            provider_code, model = parse_provider_and_model(body.model_code)
            messages = parse_messages(body.messages)

            tools = None
            if body.tools:
                tools = [tool.model_dump() for tool in body.tools]

            try:
                gateway = AIGateway(db)
                response = await gateway.stream_chat(
                    provider_code=provider_code,
                    messages=messages,
                    model=model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    top_p=body.top_p,
                    tools=tools,
                    tenant_id=tenant_admin.tenant_id,
                    user_id=tenant_admin.id,
                )
                return response
            except Exception as e:
                raise ExternalServiceException(message=_("ai.error.call_failed") + f": {str(e)}")

        @router.post("/embedding", summary="文本向量化")
        @action_create("action.ai_gateway.embedding")
        async def embedding(
            request: Request,
            db: DbSession,
            tenant_admin: ActiveTenantAdmin,
            body: EmbeddingRequest,
        ):
            """
            文本向量化

            权限: ai_gateway:embedding
            """
            provider_code, model = parse_provider_and_model(body.model_code)

            try:
                gateway = AIGateway(db)
                response = await gateway.embedding(
                    provider_code=provider_code,
                    texts=body.texts,
                    model=model,
                    tenant_id=tenant_admin.tenant_id,
                )
                return success(data=response.__dict__, message=_("common.success"))
            except Exception as e:
                raise ExternalServiceException(message=_("ai.error.embedding_failed") + f": {str(e)}")


# 导出路由器
router = TenantAIGatewayController.get_router()

__all__ = ["router", "TenantAIGatewayController"]
