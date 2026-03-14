"""
AI Gateway Unified Call Interface (Facade)
AI 网关统一调用接口（门面类）

Provides a unified AI call interface, dispatching to corresponding adapters by provider code.
Retry/Key rotation delegated to RetryService; usage/quota/logging delegated to UsageRecorder.
提供统一的 AI 调用接口，内部根据供应商代码分发到对应适配器。
重试/Key 轮换委托 RetryService，使用量/配额/日志委托 UsageRecorder。
"""

import asyncio
import time
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters import AdapterRegistry
from app.ai.cache import AIResponseCache
from app.ai.exceptions import (
    AIGatewayError,
    is_retryable,
)
from app.ai.failover import FailoverService
from app.ai.retry_service import (
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MULTIPLIER,
    RetryService,
)
from app.ai.sse import SSEStreamingResponse
from app.ai.types import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageGenerationResponse,
    TestModelResult,
    messages_to_dicts,
)
from app.ai.usage_recorder import UsageRecorder
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import CallStatusEnum, RequestTypeEnum, UserTypeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai import AIModel, AIProvider, ProviderApiKey
from app.repositories.ai import (
    AIModelRepository,
    AIProviderRepository,
    ProviderApiKeyRepository,
)
from app.services.ai.metering_service import CostCalculator, TokenCounter

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
        self.failover = FailoverService(db)
        self.retry_service = RetryService(self.api_key_repo)
        self.usage_recorder = UsageRecorder(db)

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
        tenant_id: int | None = None,
        user_id: int | None = None,
        **kwargs
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
        start_time = time.time()

        # Get provider, API Key, and model info / 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id

        # 1. Check cache (only enabled when temperature == 0) / 检查缓存（仅 temperature == 0 时启用）
        use_cache = temperature == 0 and not stream
        cache_key = None

        if use_cache:
            cache_key = AIResponseCache._generate_cache_key(
                provider_code=provider_code,
                model=model,
                messages=messages_to_dicts(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )

            cached_response = await AIResponseCache.get(cache_key)
            if cached_response:
                logger.info("Cache hit: key=%s", cache_key)
                return ChatResponse(**cached_response)

        # 2. Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 检查配额（仅企业调用）
        estimated_input = 0
        if tenant_id:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
            await self.usage_recorder.check_rate_and_quota(tenant_id, model_id, ai_model, estimated_input)

        # 4. Call adapter (with exponential backoff retry + failover) / 调用适配器（含指数退避重试 + 故障转移）
        try:
            response, retry_count, used_api_key = await self.retry_service.execute_with_retry(
                provider=provider,
                api_key=api_key,
                model=model,
                call_fn=lambda adapter: adapter.chat(
                    messages=messages, model=model, temperature=temperature,
                    max_tokens=max_tokens, top_p=top_p, stream=stream,
                    tools=tools, **kwargs,
                ),
                tenant_id=tenant_id,
            )
        except AIGatewayError as original_error:
            # Try failover to fallback model / 尝试故障转移到备用模型
            fallback_model = await self.failover.get_fallback_model(model_id)
            if not fallback_model:
                await self.usage_recorder.log_call_failure(
                    error=original_error,
                    start_time=start_time,
                    provider=provider,
                    model=model,
                    model_id=model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    request_type=RequestTypeEnum.CHAT.value,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
                raise

            logger.info(
                "Fallback attempt: original_model=%s fallback_model=%s",
                model, fallback_model.code,
            )

            try:
                fb_provider, fb_api_key = await self.get_provider_and_key(
                    fallback_model.provider.code, tenant_id
                )
                response, retry_count, used_api_key = await self.retry_service.execute_with_retry(
                    provider=fb_provider,
                    api_key=fb_api_key,
                    model=fallback_model.code,
                    call_fn=lambda adapter: adapter.chat(
                        messages=messages, model=fallback_model.code,
                        temperature=temperature, max_tokens=max_tokens,
                        top_p=top_p, stream=stream, tools=tools, **kwargs,
                    ),
                    tenant_id=tenant_id,
                )
                # Update references for subsequent metering / 更新引用用于后续计量
                provider = fb_provider
                api_key = fb_api_key
                ai_model = fallback_model
                model_id = fallback_model.id
                model = fallback_model.code
                logger.info(
                    "Fallback succeeded: fallback_model=%s",
                    fallback_model.code,
                )
            except (AIGatewayError, NotFoundException, BusinessException):
                logger.warning(
                    "Fallback failed: fallback_model=%s",
                    fallback_model.code,
                )
                await self.usage_recorder.log_call_failure(
                    error=original_error,
                    start_time=start_time,
                    provider=provider,
                    model=model,
                    model_id=model_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    request_type=RequestTypeEnum.CHAT.value,
                    tenant_id=tenant_id,
                    user_id=user_id,
                )
                raise original_error

        # 5. Calculate latency and usage / 计算延迟和使用量
        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = response.input_tokens or 0
        output_tokens = response.output_tokens or 0
        total_tokens = response.total_tokens or (input_tokens + output_tokens)

        cost = CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens) if ai_model else 0

        # 6. Update API Key usage count / 更新 API Key 使用计数
        used_api_key.increment_usage()

        # 7. Record usage and logs / 记录使用量和日志
        if tenant_id:
            try:
                await self.usage_recorder.record_usage_and_adjust(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    request_type=RequestTypeEnum.CHAT.value,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    estimated_input=estimated_input,
                    latency_ms=latency_ms,
                    user_id=user_id,
                )

                # Build request data (with retry info) / 构建请求数据（含重试信息）
                request_data = {
                    "messages": messages_to_dicts(messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "tools": tools,
                }
                if retry_count > 0:
                    request_data["_retry_count"] = retry_count

                # Async record call log / 异步记录调用日志
                await self.usage_recorder.call_log_service.log_call_async(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    provider_id=provider.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    request_data=request_data,
                    response_data=UsageRecorder.serialize_response(response),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    latency_ms=latency_ms,
                    status=CallStatusEnum.SUCCESS.value,
                    user_id=user_id,
                    user_type=UserTypeEnum.TENANT_ADMIN.value,
                )

            except Exception as e:
                logger.error("Record usage failed: %s", str(e))

        await self.db.commit()

        # 8. Write cache (only when temperature == 0) / 写缓存（仅 temperature == 0 时缓存）
        if use_cache and cache_key:
            try:
                await AIResponseCache.set(
                    cache_key=cache_key,
                    response_data=UsageRecorder.serialize_response(response),
                    ttl=settings.AI_CACHE_TTL,
                )
            except Exception as e:
                logger.error("Cache set failed: %s", str(e))

        return response

    async def stream_chat(
        self,
        provider_code: str,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        **kwargs
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
        start_time = time.time()

        # Get provider, API Key, and model info (before creating generator) / 获取供应商、API Key 和模型信息（在创建生成器之前）
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        # Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 配额检查（仅企业调用）
        estimated_input = 0
        if tenant_id:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
            await self.usage_recorder.check_rate_and_quota(tenant_id, ai_model.id, ai_model, estimated_input)

        async def generate_chunks() -> AsyncIterator[ChatChunk]:
            """Internal async generator using pre-fetched provider, api_key, ai_model.
            内部异步生成器，使用已获取的 provider, api_key, ai_model。

            With exponential backoff retry, API Key rotation, and failover.
            带指数退避重试、API Key 轮换和故障转移。
            """
            nonlocal api_key, provider, ai_model
            current_key = api_key

            try:
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        # Create adapter instance / 创建适配器实例
                        adapter = AdapterRegistry.create_adapter(
                            provider_type=provider.type,
                            api_key=current_key.decrypt_key(),
                            base_url=provider.base_url,
                        )

                        # Call adapter streaming interface / 调用适配器流式接口
                        logger.info(
                            "Gateway stream call: provider=%s model=%s",
                            provider_code, model,
                        )

                        async for chunk in adapter.stream_chat(
                            messages=messages,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            top_p=top_p,
                            tools=tools,
                            **kwargs,
                        ):
                            yield chunk

                        # Log on retry success / 重试成功时记录日志
                        if attempt > 0:
                            logger.info(
                                "Stream retry succeeded: provider=%s model=%s attempt=%s",
                                provider_code, model, attempt,
                            )

                        # Update outer api_key reference / 更新外层 api_key 引用
                        api_key = current_key
                        return  # Streaming completed successfully / 流式传输成功完成

                    except AIGatewayError as e:
                        # Non-retryable exception, raise immediately / 不可重试的异常直接抛出
                        if not is_retryable(e):
                            logger.error(
                                "Non-retryable error: provider=%s model=%s error_code=%s error=%s",
                                provider_code, model, e.error_code, str(e),
                            )
                            raise

                        # Max retries exhausted / 已达最大重试次数
                        if attempt >= MAX_RETRIES:
                            logger.error(
                                "Max retries exhausted: provider=%s model=%s attempts=%s error=%s",
                                provider_code, model, attempt + 1, str(e),
                            )
                            raise

                        # Calculate backoff delay / 计算退避延迟
                        delay = RETRY_BASE_DELAY * (RETRY_MULTIPLIER ** attempt)
                        if e.retry_after and e.retry_after > delay:
                            delay = float(e.retry_after)

                        logger.warning(
                            "Retrying after error: provider=%s model=%s attempt=%s delay=%.1fs error_code=%s error=%s",
                            provider_code, model, attempt, delay, e.error_code, str(e),
                        )

                        # Try switching API Key / 尝试切换 API Key
                        next_key = await self.retry_service.get_next_api_key(
                            provider_id=provider.id,
                            current_key_id=current_key.id,
                            tenant_id=tenant_id,
                        )
                        if next_key:
                            logger.info(
                                "Switching API key: provider=%s old_key=%s new_key=%s",
                                provider_code, current_key.id, next_key.id,
                            )
                            current_key = next_key

                        await asyncio.sleep(delay)

            except AIGatewayError as original_error:
                # All retries on primary model failed, attempt failover / 主模型所有重试失败，尝试故障转移
                fallback_model = await self.failover.get_fallback_model(ai_model.id)
                if not fallback_model:
                    await self.usage_recorder.log_call_failure(
                        error=original_error,
                        start_time=start_time,
                        provider=provider,
                        model=model,
                        model_id=ai_model.id,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        tools=tools,
                        request_type=RequestTypeEnum.CHAT.value,
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                    raise

                logger.info(
                    "Fallback attempt: original_model=%s fallback_model=%s",
                    model, fallback_model.code,
                )

                try:
                    fb_provider, fb_api_key = await self.get_provider_and_key(
                        fallback_model.provider.code, tenant_id
                    )
                    fb_adapter = AdapterRegistry.create_adapter(
                        provider_type=fb_provider.type,
                        api_key=fb_api_key.decrypt_key(),
                        base_url=fb_provider.base_url,
                    )

                    async for chunk in fb_adapter.stream_chat(
                        messages=messages,
                        model=fallback_model.code,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        tools=tools,
                        **kwargs,
                    ):
                        yield chunk

                    # Update references for on_complete callback / 更新引用供 on_complete 回调使用
                    api_key = fb_api_key
                    provider = fb_provider
                    ai_model = fallback_model
                    logger.info(
                        "Fallback succeeded: fallback_model=%s",
                        fallback_model.code,
                    )
                except (AIGatewayError, NotFoundException, BusinessException):
                    logger.warning(
                        "Fallback failed: fallback_model=%s",
                        fallback_model.code,
                    )
                    await self.usage_recorder.log_call_failure(
                        error=original_error,
                        start_time=start_time,
                        provider=provider,
                        model=model,
                        model_id=ai_model.id,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        tools=tools,
                        request_type=RequestTypeEnum.CHAT.value,
                        tenant_id=tenant_id,
                        user_id=user_id,
                    )
                    raise original_error

        # Create completion callback / 创建完成回调
        async def on_complete(input_tokens: int, output_tokens: int, total_tokens: int):
            """Stream completion callback / 流式完成回调"""
            if provider and api_key and ai_model:
                # Calculate cost and latency / 计算费用和延迟
                cost = CostCalculator.calculate_cost(
                    ai_model, input_tokens, output_tokens
                )
                stream_latency_ms = int((time.time() - start_time) * 1000)

                # Update API Key usage count and record usage (with TPM/quota correction + call log) / 更新 API Key 使用计数并记录使用量（含 TPM/配额校正 + 调用日志）
                await self.usage_recorder.on_stream_complete(
                    provider=provider,
                    api_key=api_key,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    model_id=ai_model.id,
                    estimated_input=estimated_input,
                    latency_ms=stream_latency_ms,
                )

        # Create SSE streaming response / 创建 SSE 流式响应
        sse_response = SSEStreamingResponse(
            chunk_iterator=generate_chunks(),
            db=self.db,
            on_complete=on_complete,
        )

        return sse_response.response()

    async def embedding(
        self,
        provider_code: str,
        texts: list[str],
        model: str,
        tenant_id: int | None = None,
        user_id: int | None = None,
        **kwargs
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
        start_time = time.time()

        # Get provider, API Key, and model info / 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id

        # 1. Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 配额检查（仅企业调用）
        estimated_input = 0
        if tenant_id:
            estimated_input = TokenCounter.count_messages_tokens(
                [{"role": "user", "content": t} for t in texts]
            )
            await self.usage_recorder.check_rate_and_quota(tenant_id, model_id, ai_model, estimated_input)

        # 3. Call adapter (with exponential backoff retry + API Key rotation) / 调用适配器（含指数退避重试 + API Key 轮换）
        response, _retry_count, used_api_key = await self.retry_service.execute_with_retry(
            provider=provider,
            api_key=api_key,
            model=model,
            call_fn=lambda adapter: adapter.embedding(
                texts=texts, model=model, **kwargs,
            ),
            tenant_id=tenant_id,
            log_key="ai.log.gateway_embedding_call",
        )

        # 4. Calculate latency and usage / 计算延迟和使用量
        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = response.input_tokens or 0
        total_tokens = response.total_tokens or input_tokens

        cost = CostCalculator.calculate_cost(ai_model, input_tokens, 0) if ai_model else 0

        # 5. Update API Key usage count (using actual successful key, may have rotated) / 更新 API Key 使用计数（使用实际成功的 Key，重试可能已轮换）
        used_api_key.increment_usage()

        # 6. Record usage and logs / 记录使用量和日志
        if tenant_id:
            try:
                await self.usage_recorder.record_usage_and_adjust(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    request_type=RequestTypeEnum.EMBEDDING.value,
                    input_tokens=input_tokens,
                    output_tokens=0,
                    total_tokens=total_tokens,
                    cost=cost,
                    estimated_input=estimated_input,
                    latency_ms=latency_ms,
                    user_id=user_id,
                )

                # Build request data / 构建请求数据
                request_data = {
                    "texts": texts[:3],
                    "text_count": len(texts),
                }

                # Async record call log / 异步记录调用日志
                await self.usage_recorder.call_log_service.log_call_async(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    provider_id=provider.id,
                    request_type=RequestTypeEnum.EMBEDDING.value,
                    request_data=request_data,
                    response_data={
                        "input_tokens": input_tokens,
                        "total_tokens": total_tokens,
                        "embedding_count": len(response.embeddings),
                    },
                    input_tokens=input_tokens,
                    output_tokens=0,
                    total_tokens=total_tokens,
                    cost=cost,
                    latency_ms=latency_ms,
                    status=CallStatusEnum.SUCCESS.value,
                    user_id=user_id,
                    user_type=UserTypeEnum.TENANT_ADMIN.value,
                )

            except Exception as e:
                logger.error("Record usage failed: %s", str(e))

        await self.db.commit()

        return response

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
        start_time = time.time()

        # Get provider, API Key, and model info / 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id

        # Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 配额检查（仅企业调用）
        # Image generation uses fixed token estimate (cannot predict precisely, use 1000 as baseline) / 生图按固定 token 估算（无法精确预估，使用 1000 作为基准）
        estimated_input = 0
        if tenant_id:
            estimated_input = 1000 * n
            await self.usage_recorder.check_rate_and_quota(
                tenant_id, model_id, ai_model, estimated_input,
            )

        # Call adapter (with retry) / 调用适配器（含重试）
        response, _retry_count, used_api_key = await self.retry_service.execute_with_retry(
            provider=provider,
            api_key=api_key,
            model=model,
            call_fn=lambda adapter: adapter.generate_image(
                prompt=prompt, model=model, size=size,
                quality=quality, style=style, n=n, **kwargs,
            ),
            tenant_id=tenant_id,
            log_key="ai.log.gateway_image_call",
        )

        # Calculate latency / 计算延迟
        latency_ms = int((time.time() - start_time) * 1000)

        # No token consumption for image generation, metered per request / 生图无 token 消耗，按次计量
        input_tokens = estimated_input
        output_tokens = 0
        total_tokens = input_tokens

        cost = CostCalculator.calculate_cost(
            ai_model, input_tokens, output_tokens,
        ) if ai_model else 0

        # Update API Key usage count / 更新 API Key 使用计数
        used_api_key.increment_usage()

        # Record usage and logs / 记录使用量和日志
        if tenant_id:
            try:
                await self.usage_recorder.record_usage_and_adjust(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    request_type=RequestTypeEnum.IMAGE.value,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    estimated_input=estimated_input,
                    latency_ms=latency_ms,
                    user_id=user_id,
                )

                request_data = {
                    "prompt": prompt[:200],
                    "size": size,
                    "quality": quality,
                    "n": n,
                }

                await self.usage_recorder.call_log_service.log_call_async(
                    tenant_id=tenant_id,
                    model_id=model_id,
                    provider_id=provider.id,
                    request_type=RequestTypeEnum.IMAGE.value,
                    request_data=request_data,
                    response_data={
                        "image_count": len(response.images),
                        "revised_prompt": response.revised_prompt,
                    },
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost=cost,
                    latency_ms=latency_ms,
                    status=CallStatusEnum.SUCCESS.value,
                    user_id=user_id,
                    user_type=UserTypeEnum.TENANT_ADMIN.value,
                )

            except Exception as e:
                logger.error("Record image generation usage failed: %s", str(e))

        await self.db.commit()

        return response

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
        # Query provider via Repository / 通过 Repository 查询供应商
        provider = await self.provider_repo.get_by_id(provider_id)

        if not provider or not provider.is_active:
            return TestModelResult(
                connected=False,
                error=_("ai.provider_not_found"),
                model=model_code,
            )

        # Get platform-level API Key via Repository / 通过 Repository 获取平台级 API Key
        api_key = await self.api_key_repo.get_available_key(
            provider_id=provider.id,
            tenant_id=None,
        )

        if not api_key or not api_key.is_available():
            return TestModelResult(
                connected=False,
                error=_("ai.no_api_key"),
                model=model_code,
                provider=provider.code,
            )

        # Detect model type (embedding models need different test approach) / 检测模型类型（embedding 模型需要不同的测试方式）
        ai_model = await self._get_model(model_code, provider.id)
        is_embedding = ai_model and ai_model.type == "embedding"

        # Record start time / 记录开始时间
        start_time = time.time()

        try:
            # Create adapter / 创建适配器
            adapter = AdapterRegistry.create_adapter(
                provider_type=provider.type,
                api_key=api_key.decrypt_key(),
                base_url=provider.base_url,
            )

            if is_embedding:
                # Embedding model: send test text, verify returned vectors / Embedding 模型：发送测试文本，验证返回向量
                response = await adapter.embedding(
                    texts=[test_prompt or "Hello"],
                    model=model_code,
                )
                latency_ms = int((time.time() - start_time) * 1000)
                dim = len(response.embeddings[0]) if response.embeddings else 0

                return TestModelResult(
                    connected=True,
                    latency_ms=latency_ms,
                    input_tokens=response.input_tokens or 0,
                    total_tokens=response.total_tokens or 0,
                    response_text=f"Embedding OK: dim={dim}",
                    model=model_code,
                    provider=provider.code,
                )

            # Chat model / Chat 模型
            messages = [
                ChatMessage(role="user", content=test_prompt),
            ]

            if stream:
                # Streaming response test (take first 5 chunks only) / 流式响应测试（只取前 5 个 chunk）
                response_chunks = []
                stream_gen = adapter.stream_chat(
                    messages=messages,
                    model=model_code,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                try:
                    async for chunk in stream_gen:
                        response_chunks.append(chunk.delta or "")
                        if len(response_chunks) >= 5:
                            break
                finally:
                    await stream_gen.aclose()

                latency_ms = int((time.time() - start_time) * 1000)
                response_text = "".join(response_chunks)

                return TestModelResult(
                    connected=True,
                    latency_ms=latency_ms,
                    response_text=response_text,
                    model=model_code,
                    provider=provider.code,
                )
            else:
                # Non-streaming response test / 非流式响应测试
                response = await adapter.chat(
                    messages=messages,
                    model=model_code,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # Extract response text / 提取响应文本
                response_text = response.message.content or ""

                return TestModelResult(
                    connected=True,
                    latency_ms=latency_ms,
                    input_tokens=response.input_tokens or 0,
                    output_tokens=response.output_tokens or 0,
                    total_tokens=response.total_tokens or 0,
                    response_text=response_text,
                    model=model_code,
                    provider=provider.code,
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("Model test failed: provider=%s model=%s error=%s", provider.code, model_code, str(e))

            return TestModelResult(
                connected=False,
                latency_ms=latency_ms,
                error=str(e),
                model=model_code,
                provider=provider.code,
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
        # Query provider via Repository / 通过 Repository 查询供应商
        provider = await self.provider_repo.get_by_code(provider_code)

        if not provider or not provider.is_active:
            raise NotFoundException(message=_("ai.provider_not_found"))

        # Get available API Key via Repository / 通过 Repository 获取可用 API Key
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
        return await self.model_repo.get_active_by_name_and_provider(model_name, provider_id)

__all__ = [
    "AIGateway",
]
