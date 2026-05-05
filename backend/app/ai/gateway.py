"""
AI Gateway Unified Call Interface (Facade) / AI 网关统一调用接口（门面类）

Provides a unified AI call interface, dispatching to corresponding adapters by provider code.
Retry/Key rotation delegated to RetryService; usage/quota/logging delegated to UsageRecorder.
提供统一的 AI 调用接口，内部根据供应商代码分发到对应适配器。
重试/Key 轮换委托 RetryService，使用量/配额/日志委托 UsageRecorder。
"""

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters import AdapterRegistry
from app.ai.cache import AIResponseCache
from app.ai.failover import FailoverService
from app.ai.gateway_support import (
    GatewayCallLogBridge,
    GatewayDispatcher,
)
from app.ai.gateway_support import (
    execute_chat as execute_chat_impl,
)
from app.ai.gateway_support import (
    execute_embedding as execute_embedding_impl,
)
from app.ai.gateway_support import (
    execute_image_generation as execute_image_generation_impl,
)
from app.ai.gateway_support import (
    execute_stream_chat as execute_stream_chat_impl,
)
from app.ai.gateway_support import (
    execute_test_model as execute_test_model_impl,
)
from app.ai.gateway_support.facade_mixins import GatewayFacadeMixin
from app.ai.gateway_support.retry_orchestrator import GatewayRetryOrchestrator
from app.ai.retry_service import RetryService
from app.ai.runtime.usage_metrics import CostCalculator, TokenCounter
from app.ai.types import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageGenerationResponse,
    TestModelResult,
)
from app.ai.usage_recorder import UsageRecorder
from app.core.config import settings
from app.core.logging import LogManager
from app.enums.ai import CallTypeEnum
from app.repositories.ai import (
    AIModelRepository,
    AIProviderRepository,
    ProviderApiKeyRepository,
)

logger = LogManager.get_logger("ai")


class AIGateway(GatewayFacadeMixin):
    """
    AI Gateway / AI 网关

    Provides a unified AI call interface, abstracting away provider API differences.
    Supports exponential backoff retry and API Key rotation.
    提供统一的 AI 调用接口，屏蔽不同供应商 API 差异。
    支持指数退避重试和 API Key 轮换。
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize AI Gateway.
        初始化 AI 网关。

        Args:
            db: Database session / 数据库会话
        """
        self.db = db
        self.provider_repo = AIProviderRepository(db)
        self.api_key_repo = ProviderApiKeyRepository(db)
        self.model_repo = AIModelRepository(db)
        self.dispatcher = GatewayDispatcher(db)
        self.failover = FailoverService(db)
        self.retry_service = RetryService(self.api_key_repo)
        self.retry_orchestrator = GatewayRetryOrchestrator(self.retry_service)
        self.usage_recorder = UsageRecorder(db)
        self.call_log_bridge = GatewayCallLogBridge()

    async def chat(
        self,
        provider_code: str,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        stream: bool = False,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy_family: str | None = None,
        tool_use_policy_mode: str | None = None,
        allowed_tool_names: list[str] | None = None,
        breach_retry_result: str | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
        **kwargs,
    ) -> ChatResponse:
        """
        Chat conversation (unified interface, full call chain).
        聊天对话（统一接口，完整调用链路）。

        Call chain / 调用链路:
        Cache check → Rate limit → Quota check → Get API Key → Call adapter (with retry) → Log → Update usage → Write cache
        缓存检查 → 限流检查 → 配额检查 → 获取 API Key → 调用适配器(含重试) → 记录日志 → 更新用量 → 写缓存

        Args:
            provider_code: Provider code (e.g. openai_compatible) / 供应商代码
            messages: Chat message list / 聊天消息列表
            model: Model name / 模型名称
            temperature: Temperature parameter / 温度参数
            max_tokens: Max generation tokens / 最大生成 tokens
            top_p: Nucleus sampling parameter / 核采样参数
            stream: Whether to use streaming / 是否使用流式响应
            tools: Tool list / 工具列表
            tenant_id: Tenant ID (for tenant-level API Key) / 企业 ID
            user_id: User ID (for usage recording) / 用户 ID
            **kwargs: Additional parameters / 其他参数

        Returns:
            ChatResponse: Chat response / 聊天响应

        Raises:
            AIGatewayError: AI gateway exception (all subclasses) / AI 网关异常
            RateLimitExceeded: Rate limit exceeded / 速率限制超出
            QuotaExceeded: Quota exceeded / 配额超出
        """
        return await execute_chat_impl(
            self,
            provider_code=provider_code,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
            tools=tools,
            tool_choice=tool_choice,
            all_tool_names=all_tool_names,
            tool_use_policy_family=tool_use_policy_family,
            tool_use_policy_mode=tool_use_policy_mode,
            allowed_tool_names=allowed_tool_names,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            agent_id=agent_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            call_type=call_type,
            adapter_registry=AdapterRegistry,
            token_counter=TokenCounter,
            cost_calculator=CostCalculator,
            usage_recorder_cls=UsageRecorder,
            response_cache=AIResponseCache,
            settings_obj=settings,
            **kwargs,
        )

    async def stream_chat(
        self,
        provider_code: str,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy_family: str | None = None,
        tool_use_policy_mode: str | None = None,
        allowed_tool_names: list[str] | None = None,
        breach_retry_result: str | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict | None = None,
        routed_model_id: int | None = None,
        route_reason: str | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
        **kwargs,
    ) -> StreamingResponse:
        """
        Chat conversation (streaming interface, returns SSE).
        聊天对话（流式接口，返回 SSE）。

        Args:
            provider_code: Provider code / 供应商代码
            messages: Chat message list / 聊天消息列表
            model: Model name / 模型名称
            temperature: Temperature parameter / 温度参数
            max_tokens: Max generation tokens / 最大生成 tokens
            top_p: Nucleus sampling parameter / 核采样参数
            tools: Tool list / 工具列表
            tenant_id: Tenant ID / 企业 ID
            user_id: User ID (for usage recording) / 用户 ID
            **kwargs: Additional parameters / 其他参数

        Returns:
            StreamingResponse: FastAPI SSE streaming response / FastAPI SSE 流式响应

        Raises:
            NotFoundException: Model not found / 模型不存在
            RateLimitExceeded: Rate limit exceeded / 速率限制超出
            QuotaExceeded: Quota exceeded / 配额超出
        """
        return await execute_stream_chat_impl(
            self,
            provider_code=provider_code,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            all_tool_names=all_tool_names,
            tool_use_policy_family=tool_use_policy_family,
            tool_use_policy_mode=tool_use_policy_mode,
            allowed_tool_names=allowed_tool_names,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            agent_id=agent_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            routed_model_id=routed_model_id,
            route_reason=route_reason,
            call_type=call_type,
            adapter_registry=AdapterRegistry,
            token_counter=TokenCounter,
            cost_calculator=CostCalculator,
            **kwargs,
        )

    async def embedding(
        self,
        provider_code: str,
        texts: list[str],
        model: str,
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        billing_context: dict | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
        **kwargs,
    ) -> EmbeddingResponse:
        """
        Text embedding (unified interface, full call chain).
        文本嵌入（统一接口，完整调用链路）。

        Call chain / 调用链路:
        Rate limit → Quota check → Get API Key → Call adapter → Log → Update usage
        限流检查 → 配额检查 → 获取 API Key → 调用适配器 → 记录日志 → 更新用量

        Args:
            provider_code: Provider code / 供应商代码
            texts: Text list / 文本列表
            model: Model name / 模型名称
            tenant_id: Tenant ID / 企业 ID
            user_id: User ID (for usage recording) / 用户 ID
            **kwargs: Additional parameters / 其他参数

        Returns:
            EmbeddingResponse: Embedding vector response / 嵌入向量响应
        """
        return await execute_embedding_impl(
            self,
            provider_code=provider_code,
            texts=texts,
            model=model,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            billing_context=billing_context,
            call_type=call_type,
            token_counter=TokenCounter,
            cost_calculator=CostCalculator,
            **kwargs,
        )

    async def generate_image(
        self,
        provider_code: str,
        prompt: str,
        model: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        n: int = 1,
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict | None = None,
        call_type: str = CallTypeEnum.MAIN_CHAT.value,
        **kwargs,
    ) -> ImageGenerationResponse:
        """
        Image generation (unified interface, full call chain).
        图像生成（统一接口，完整调用链路）。

        Call chain / 调用链路:
        Rate limit → Quota check → Get API Key → Call adapter (with retry) → Log → Update usage
        限流检查 → 配额检查 → 获取 API Key → 调用适配器(含重试) → 记录日志 → 更新用量

        Args:
            provider_code: Provider code / 供应商代码
            prompt: Generation prompt / 生成提示词
            model: Model name (e.g. dall-e-3) / 模型名称
            size: Image size / 图片尺寸
            quality: Quality (standard / hd) / 质量
            style: Style (vivid / natural) / 风格
            n: Number to generate / 生成数量
            tenant_id: Tenant ID / 企业 ID
            user_id: User ID / 用户 ID
            **kwargs: Additional parameters / 其他参数

        Returns:
            ImageGenerationResponse: Image generation response / 图像生成响应
        """
        return await execute_image_generation_impl(
            self,
            provider_code=provider_code,
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            style=style,
            n=n,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            agent_id=agent_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            call_type=call_type,
            cost_calculator=CostCalculator,
            **kwargs,
        )

    async def test_model(
        self,
        provider_id: int,
        model_code: str,
        test_prompt: str = "Hello",
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = 500,
    ) -> TestModelResult:
        """
        Test model connectivity and response quality (no logging).
        测试模型连通性和响应质量（不记录日志）。

        Used by Admin to verify model configuration; no call logs or metering.
        用于 Admin 端测试模型配置是否正确，不记录调用日志和计量。

        Args:
            provider_id: Provider ID / 供应商 ID
            model_code: Model code / 模型代码
            test_prompt: Test prompt / 测试提示词
            stream: Whether to use streaming / 是否使用流式响应
            temperature: Temperature parameter / 温度参数
            max_tokens: Max generation tokens / 最大生成 tokens

        Returns:
            TestModelResult: Typed test result / 类型化测试结果
        """
        return await execute_test_model_impl(
            self,
            provider_id=provider_id,
            model_code=model_code,
            test_prompt=test_prompt,
            stream=stream,
            temperature=temperature,
            max_tokens=max_tokens,
            adapter_registry=AdapterRegistry,
        )


__all__ = [
    "AIGateway",
]
