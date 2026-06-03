"""
平台端 AI 网关调用 API / Platform AI Gateway API

提供平台管理员 AI 网关统一调用接口，用于测试和系统内部调用
Provides platform admin unified AI gateway call interface for testing and internal use.
"""

from fastapi import Request

from app.ai.exceptions import AIGatewayError
from app.ai.gateway import AIGateway
from app.ai.internal_ai_service import InternalAIService
from app.ai.quota_exceptions import QuotaExceeded
from app.ai.rate_limiter import RateLimitExceeded
from app.ai.utils import parse_messages, parse_provider_and_model
from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_controller import GlobalController
from app.core.deps import ActiveAdmin, DbSession
from app.core.i18n import _
from app.core.response import build_exception_debug, success
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
    ModelTestRequest,
)


@permission_resource(
    resource="ai_gateway",
    name="menu.admin.ai_gateway",
    scope=PermissionScope.ADMIN,
    parent_resource="ai_infra",
)
class AdminAIGatewayController(GlobalController):
    """
    AI 网关控制器 (Admin) / AI Gateway Controller (Admin)

    平台管理员可直接调用 AI 网关进行测试 / Platform admin can directly call AI gateway for testing
    """

    prefix = "/ai/gateway"
    tags = [_("menu.tags.admin_ai_gateway")]

    def _register_routes(self) -> None:
        router = self.router

        @router.post("/chat", summary="AI 聊天对话（非流式）")
        @action_create("action.ai_gateway.chat")
        async def chat(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: ChatRequest,
        ):
            """
            AI 聊天对话（非流式） / AI chat conversation (non-streaming)

            权限 / Permission: ai_gateway:chat
            """
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
                    tenant_id=PLATFORM_TENANT_ID,
                    user_id=admin.id,
                    user_type="admin",
                )
                return success(data=response.__dict__)
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
            admin: ActiveAdmin,
            body: ChatRequest,
        ):
            """
            AI 聊天对话（流式 SSE） / AI chat conversation (streaming SSE)

            权限 / Permission: ai_gateway:chat_stream
            """
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
                    tenant_id=PLATFORM_TENANT_ID,
                    user_id=admin.id,
                    user_type="admin",
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
            admin: ActiveAdmin,
            body: EmbeddingRequest,
        ):
            """
            文本向量化 / Text embedding

            权限 / Permission: ai_gateway:embedding
            """
            provider_code, model = parse_provider_and_model(body.model_code)

            try:
                service = InternalAIService(db)
                response = await service.embedding(
                    provider_code=provider_code,
                    texts=body.texts,
                    model=model,
                    tenant_id=PLATFORM_TENANT_ID,
                    user_id=admin.id,
                    user_type="admin",
                )
                return success(data=response.__dict__)
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

        @router.post("/test", summary="测试模型连通性")
        @action_create("action.ai_gateway.test")
        async def test_model(
            request: Request,
            db: DbSession,
            admin: ActiveAdmin,
            body: ModelTestRequest,
        ):
            """
            测试模型连通性和响应质量 / Test model connectivity and response quality

            权限 / Permission: ai_gateway:test

            不记录调用日志和计量，仅用于测试配置是否正确。
            No call logging or metering, only for testing configuration correctness.
            """
            try:
                gateway = AIGateway(db)
                result = await gateway.test_model(
                    provider_id=body.provider_id,
                    model_code=body.model_code,
                    test_prompt=body.test_prompt,
                    stream=body.stream,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                )
                return success(data=result)
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
                    message=_("ai.error.test_failed"),
                    debug=build_exception_debug(e),
                ) from e


# 导出路由器 / Export router
router = AdminAIGatewayController.get_router()

__all__ = ["router", "AdminAIGatewayController"]
