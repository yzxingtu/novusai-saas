"""
AI Gateway Unified Call Interface (Facade) / AI 网关统一调用接口（门面类）

Provides a unified AI call interface, dispatching to corresponding adapters by provider code.
Retry/Key rotation delegated to RetryService; usage/quota/logging delegated to UsageRecorder.
提供统一的 AI 调用接口，内部根据供应商代码分发到对应适配器。
重试/Key 轮换委托 RetryService，使用量/配额/日志委托 UsageRecorder。
"""

from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters import AdapterRegistry
from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.cache import AIResponseCache
from app.ai.exceptions import ProviderTimeoutError
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
from app.ai.gateway_support.native_web_search_bridge import (
    native_web_search_call_status as native_web_search_call_status_impl,
)
from app.ai.gateway_support.native_web_search_bridge import (
    native_web_search_error_status as native_web_search_error_status_impl,
)
from app.ai.gateway_support.native_web_search_bridge import (
    raise_retryable_native_web_search_failure as raise_retryable_native_web_search_failure_impl,
)
from app.ai.gateway_support.native_web_search_gateway import (
    execute_native_web_search as execute_native_web_search_impl,
)
from app.ai.gateway_support.protocol_adapter_bridge import (
    call_chat_adapter as call_chat_adapter_impl,
)
from app.ai.gateway_support.protocol_adapter_bridge import (
    resolve_adapter_protocol_wire_api as resolve_adapter_protocol_wire_api_impl,
)
from app.ai.gateway_support.protocol_adapter_bridge import (
    resolve_gateway_protocol_wire_api as resolve_gateway_protocol_wire_api_impl,
)
from app.ai.gateway_support.protocol_adapter_bridge import (
    stream_chat_adapter as stream_chat_adapter_impl,
)
from app.ai.gateway_support.retry_orchestrator import GatewayRetryOrchestrator
from app.ai.retry_service import RetryService
from app.ai.runtime.usage_metrics import CostCalculator, TokenCounter
from app.ai.types import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageGenerationResponse,
    TestModelResult,
)
from app.ai.usage_recorder import UsageRecorder
from app.ai.web_search.types import SearchProviderRun
from app.configs.service import PLATFORM_TENANT_ID
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import CallTypeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai import AIModel, AIProvider, ProviderApiKey
from app.repositories.ai import (
    AIModelRepository,
    AIProviderRepository,
    ProviderApiKeyRepository,
)

logger = LogManager.get_logger("ai")


class AIGateway:
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

    async def _execute_with_retry(self, **kwargs):
        orchestrator = getattr(self, "retry_orchestrator", None)
        if orchestrator is not None:
            return await orchestrator.execute_with_retry(**kwargs)
        return await self.retry_service.execute_with_retry(**kwargs)

    @staticmethod
    def _should_meter_usage(tenant_id: int | None) -> bool:
        return tenant_id is not None and tenant_id > PLATFORM_TENANT_ID

    @staticmethod
    def _should_record_call_log(tenant_id: int | None) -> bool:
        return tenant_id is not None

    @staticmethod
    def _resolve_call_user_type(
        tenant_id: int | None,
        user_type: str | None = None,
    ) -> str | None:
        return GatewayCallLogBridge.resolve_call_user_type(tenant_id, user_type)

    @staticmethod
    def _build_request_log_data(
        *,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        all_tool_names: list[str] | None = None,
        retry_count: int = 0,
        tool_use_policy_family: str | None = None,
        tool_use_policy_mode: str | None = None,
        allowed_tool_names: list[str] | None = None,
        breach_retry_result: str | None = None,
        stream: bool = False,
    ) -> dict[str, object]:
        return GatewayCallLogBridge.build_request_log_data(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            all_tool_names=all_tool_names,
            retry_count=retry_count,
            tool_use_policy_family=tool_use_policy_family,
            tool_use_policy_mode=tool_use_policy_mode,
            allowed_tool_names=allowed_tool_names,
            breach_retry_result=breach_retry_result,
            stream=stream,
        )

    @staticmethod
    def _warn_policy_not_loaded(
        *,
        tools: list[dict] | None,
        tool_choice: str | None,
        conversation_id: int | None,
        agent_id: int | None,
    ) -> None:
        GatewayCallLogBridge.warn_policy_not_loaded(
            tools=tools,
            tool_choice=tool_choice,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )

    @staticmethod
    def _resolve_billing_context(
        tenant_id: int | None,
        *,
        user_id: int | None,
        user_type: str | None,
        billing_context: dict | None = None,
    ) -> dict[str, object | None]:
        return GatewayCallLogBridge.resolve_billing_context(
            tenant_id,
            user_id=user_id,
            user_type=user_type,
            billing_context=billing_context,
        )

    @staticmethod
    def _merge_model_provider_snapshots(
        billing_context: dict | None,
        *,
        provider: AIProvider | None,
        ai_model: AIModel | None,
    ) -> dict[str, object | None]:
        return GatewayCallLogBridge.merge_model_provider_snapshots(
            billing_context,
            provider=provider,
            ai_model=ai_model,
        )

    @staticmethod
    def _attach_runtime_metadata(
        payload: ChatResponse | EmbeddingResponse | ImageGenerationResponse,
        *,
        provider: AIProvider,
        ai_model: AIModel,
    ) -> None:
        GatewayCallLogBridge.attach_runtime_metadata(
            payload,
            provider=provider,
            ai_model=ai_model,
        )

    def _build_adapter_extra(
        self,
        *,
        ai_model: AIModel | None,
        tenant_id: int | None,
    ) -> dict[str, object | None]:
        return {
            "internal_db": self.db,
            "internal_tenant_id": tenant_id,
            "model_config": getattr(ai_model, "config", None),
        }

    @staticmethod
    def _resolve_effective_model_request(
        *,
        provider: AIProvider,
        ai_model: AIModel | None,
        model_code: str,
        wire_api: str | None = None,
    ) -> dict[str, Any]:
        if provider.type == "openai_compatible":
            return OpenAIAdapter.resolve_effective_model_request(
                model=model_code,
                model_config=getattr(ai_model, "config", None),
                wire_api=wire_api,
            )
        return {
            "logical_model_code": model_code,
            "upstream_model": model_code,
            "reasoning_effort": None,
            "effective_params": {},
            "applied_overrides": [],
            "ignored_overrides": [],
            "ignore_reasons": {},
            "override_source": "model_code",
        }

    @staticmethod
    def _resolve_gateway_protocol_wire_api(
        provider: AIProvider,
        *,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> str | None:
        return resolve_gateway_protocol_wire_api_impl(
            provider,
            extra_kwargs=extra_kwargs,
        )

    @staticmethod
    def _resolve_adapter_protocol_wire_api(
        adapter: Any,
        *,
        wire_api: str | None,
    ) -> str:
        return resolve_adapter_protocol_wire_api_impl(
            adapter,
            wire_api=wire_api,
        )

    async def _call_chat_adapter(
        self,
        *,
        adapter: Any,
        provider: AIProvider,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        stream: bool,
        tools: list[dict] | None,
        tool_choice: str | None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        return await call_chat_adapter_impl(
            messages=messages,
            adapter=adapter,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream,
            tools=tools,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        )

    async def _stream_chat_adapter(
        self,
        *,
        adapter: Any,
        provider: AIProvider,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in stream_chat_adapter_impl(
            adapter=adapter,
            provider=provider,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
        ):
            yield chunk

    @staticmethod
    def _raise_retryable_native_web_search_failure(
        run: SearchProviderRun,
        *,
        provider_code: str,
        model_code: str,
    ) -> SearchProviderRun:
        return raise_retryable_native_web_search_failure_impl(
            run,
            provider_code=provider_code,
            model_code=model_code,
        )

    @staticmethod
    def _native_web_search_error_status(error: Exception) -> str:
        return native_web_search_error_status_impl(error)

    @staticmethod
    def _native_web_search_call_status(status: str) -> str:
        return native_web_search_call_status_impl(status)

    async def native_web_search(
        self,
        *,
        provider_code: str,
        model: str,
        query: str,
        max_results: int,
        locale: str | None = None,
        timeout_seconds: int = 20,
        tenant_id: int | None = None,
        user_id: int | None = None,
        user_type: str | None = None,
        agent_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict | None = None,
        provider_label: str | None = None,
        backend_key: str | None = None,
        call_type: str = CallTypeEnum.INTERNAL_TOOL.value,
    ) -> SearchProviderRun:
        """
        Provider-hosted native web search with gateway governance.
        走网关治理链路的供应商原生联网搜索。
        """
        return await execute_native_web_search_impl(
            self,
            provider_code=provider_code,
            model=model,
            query=query,
            max_results=max_results,
            locale=locale,
            timeout_seconds=timeout_seconds,
            tenant_id=tenant_id,
            user_id=user_id,
            user_type=user_type,
            agent_id=agent_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            provider_label=provider_label,
            backend_key=backend_key,
            call_type=call_type,
            adapter_registry=AdapterRegistry,
            token_counter=TokenCounter,
            cost_calculator=CostCalculator,
            provider_timeout_error_cls=ProviderTimeoutError,
        )

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

    async def get_provider_and_key(
        self,
        provider_code: str,
        tenant_id: int | None = None,
    ) -> tuple[AIProvider, ProviderApiKey]:
        """
        Get provider and available API Key.
        获取供应商和可用的 API Key。

        Args:
            provider_code: Provider code / 供应商代码
            tenant_id: Tenant ID / 企业 ID

        Returns:
            (provider, API Key) tuple / (供应商, API Key) 元组

        Raises:
            NotFoundException: Provider not found / 供应商不存在
            BusinessException: No available API Key / 没有可用的 API Key
        """
        dispatcher = getattr(self, "dispatcher", None)
        if dispatcher is not None:
            return await dispatcher.resolve_provider_and_key(
                provider_code=provider_code,
                tenant_id=tenant_id,
            )

        provider = await self.provider_repo.get_by_code(provider_code)
        if not provider or not provider.is_active:
            raise NotFoundException(message=_("ai.provider_not_found"))

        api_key = await self.api_key_repo.get_available_key(
            provider_id=provider.id,
            tenant_id=tenant_id,
        )
        if not api_key:
            raise BusinessException(message=_("ai.no_api_key"))
        if not api_key.is_available():
            raise BusinessException(message=_("ai.api_key_unavailable"))
        return provider, api_key

    async def _get_model(self, model_name: str, provider_id: int) -> AIModel | None:
        """
        Get model information.
        获取模型信息。

        Args:
            model_name: Model name / 模型名称
            provider_id: Provider ID / 供应商 ID

        Returns:
            AIModel instance, or None if not found / AIModel 实例，如果不存在则返回 None
        """
        dispatcher = getattr(self, "dispatcher", None)
        if dispatcher is not None:
            return await dispatcher.resolve_model(
                model_name=model_name,
                provider_id=provider_id,
            )

        model = await self.model_repo.get_active_by_code_and_provider(
            model_name,
            provider_id,
        )
        if model is not None:
            return model
        return await self.model_repo.get_active_by_name_and_provider(
            model_name,
            provider_id,
        )


__all__ = [
    "AIGateway",
]
