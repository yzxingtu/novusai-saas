"""
AI 网关统一调用接口（门面类）

提供统一的 AI 调用接口，内部根据供应商代码分发到对应适配器。
重试/Key 轮换委托 RetryService，使用量/配额/日志委托 UsageRecorder。
"""

import asyncio
import time
from typing import AsyncIterator
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters import AdapterRegistry
from app.ai.exceptions import (
    AIGatewayError,
    is_retryable,
)
from app.ai.retry_service import (
    RetryService,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MULTIPLIER,
)
from app.ai.sse import SSEStreamingResponse
from app.ai.types import (
    ChatMessage,
    ChatResponse,
    ChatChunk,
    EmbeddingResponse,
    ImageGenerationResponse,
    TestModelResult,
    messages_to_dicts,
)
from app.ai.usage_recorder import UsageRecorder
from app.ai.cache import AIResponseCache
from app.ai.failover import FailoverService
from app.core.config import settings
from app.core.logging import LogManager
from app.core.i18n import _
from app.exceptions import NotFoundException, BusinessException
from app.models.ai import AIProvider, ProviderApiKey, AIModel
from app.repositories.ai import AIProviderRepository, AIModelRepository, ProviderApiKeyRepository
from app.services.ai.metering_service import CostCalculator, TokenCounter
from app.enums.ai import RequestTypeEnum, CallStatusEnum, UserTypeEnum

logger = LogManager.get_logger("ai")


class AIGateway:
    """
    AI 网关

    提供统一的 AI 调用接口，屏蔽不同供应商 API 差异。
    支持指数退避重试和 API Key 轮换。
    """

    def __init__(self, db: AsyncSession):
        """
        初始化 AI 网关

        Args:
            db: 数据库会话
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
        聊天对话（统一接口，完整调用链路）

        调用链路:
        缓存检查 → 限流检查 → 配额检查 → 获取 API Key → 调用适配器(含重试) → 记录日志 → 更新用量 → 写缓存

        Args:
            provider_code: 供应商代码（如 openai_compatible）
            messages: 聊天消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成 tokens
            top_p: 核采样参数
            stream: 是否使用流式响应
            tools: 工具列表
            tenant_id: 租户 ID（用于获取租户级 API Key）
            user_id: 用户 ID（用于记录使用量）
            **kwargs: 其他参数

        Returns:
            ChatResponse: 聊天响应

        Raises:
            AIGatewayError: AI 网关异常（含所有子类）
            RateLimitExceeded: 速率限制超出
            QuotaExceeded: 配额超出
        """
        start_time = time.time()

        # 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id

        # 1. 检查缓存（仅 temperature == 0 时启用）
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

        # 2. 原子检查+记录速率限制 + 检查配额（仅租户调用）
        estimated_input = 0
        if tenant_id:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
            await self.usage_recorder.check_rate_and_quota(tenant_id, model_id, ai_model, estimated_input)

        # 4. 调用适配器（含指数退避重试 + 故障转移）
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
            # 尝试故障转移到备用模型
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
                _("ai.log.fallback_attempt"),
                original_model=model,
                fallback_model=fallback_model.code,
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
                # 更新引用用于后续计量
                provider = fb_provider
                api_key = fb_api_key
                ai_model = fallback_model
                model_id = fallback_model.id
                model = fallback_model.code
                logger.info(
                    _("ai.log.fallback_succeeded"),
                    fallback_model=fallback_model.code,
                )
            except (AIGatewayError, NotFoundException, BusinessException):
                logger.warning(
                    _("ai.log.fallback_failed"),
                    fallback_model=fallback_model.code,
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

        # 5. 计算延迟和使用量
        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = response.input_tokens or 0
        output_tokens = response.output_tokens or 0
        total_tokens = response.total_tokens or (input_tokens + output_tokens)

        cost = CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens) if ai_model else 0

        # 6. 更新 API Key 使用计数
        used_api_key.increment_usage()

        # 7. 记录使用量和日志
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

                # 构建请求数据（含重试信息）
                request_data = {
                    "messages": messages_to_dicts(messages),
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "tools": tools,
                }
                if retry_count > 0:
                    request_data["_retry_count"] = retry_count

                # 异步记录调用日志
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

        # 8. 写缓存（仅 temperature == 0 时缓存）
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
        聊天对话（流式接口，返回 SSE）

        Args:
            provider_code: 供应商代码
            messages: 聊天消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成 tokens
            top_p: 核采样参数
            tools: 工具列表
            tenant_id: 租户 ID
            user_id: 用户 ID（用于记录使用量）
            **kwargs: 其他参数

        Returns:
            StreamingResponse: FastAPI SSE 流式响应

        Raises:
            NotFoundException: 模型不存在
            RateLimitExceeded: 速率限制超出
            QuotaExceeded: 配额超出
        """
        start_time = time.time()

        # 获取供应商、API Key 和模型信息（在创建生成器之前）
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        # 原子检查+记录速率限制 + 配额检查（仅租户调用）
        estimated_input = 0
        if tenant_id:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
            await self.usage_recorder.check_rate_and_quota(tenant_id, ai_model.id, ai_model, estimated_input)

        async def generate_chunks() -> AsyncIterator[ChatChunk]:
            """内部异步生成器，使用已获取的 provider, api_key, ai_model

            带指数退避重试、API Key 轮换和故障转移。
            """
            nonlocal api_key, provider, ai_model
            current_key = api_key

            try:
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        # 创建适配器实例
                        adapter = AdapterRegistry.create_adapter(
                            provider_type=provider.type,
                            api_key=current_key.decrypt_key(),
                            base_url=provider.base_url,
                        )

                        # 调用适配器流式接口
                        logger.info(
                            _("ai.log.gateway_stream_call"),
                            provider=provider_code,
                            model=model,
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

                        # 重试成功时记录日志
                        if attempt > 0:
                            logger.info(
                                _("ai.log.retry_succeeded"),
                                provider=provider_code,
                                model=model,
                                attempt=attempt,
                            )

                        # 更新外层 api_key 引用
                        api_key = current_key
                        return  # 流式传输成功完成

                    except AIGatewayError as e:
                        # 不可重试的异常直接抛出
                        if not is_retryable(e):
                            logger.error(
                                _("ai.log.non_retryable_error"),
                                provider=provider_code,
                                model=model,
                                error_code=e.error_code,
                                error=str(e),
                            )
                            raise

                        # 已达最大重试次数
                        if attempt >= MAX_RETRIES:
                            logger.error(
                                _("ai.log.max_retries_exhausted"),
                                provider=provider_code,
                                model=model,
                                attempts=attempt + 1,
                                error=str(e),
                            )
                            raise

                        # 计算退避延迟
                        delay = RETRY_BASE_DELAY * (RETRY_MULTIPLIER ** attempt)
                        if e.retry_after and e.retry_after > delay:
                            delay = float(e.retry_after)

                        logger.warning(
                            _("ai.log.retrying_after_error"),
                            provider=provider_code,
                            model=model,
                            attempt=attempt,
                            delay_seconds=delay,
                            error_code=e.error_code,
                            error=str(e),
                        )

                        # 尝试切换 API Key
                        next_key = await self.retry_service.get_next_api_key(
                            provider_id=provider.id,
                            current_key_id=current_key.id,
                            tenant_id=tenant_id,
                        )
                        if next_key:
                            logger.info(
                                _("ai.log.switching_api_key"),
                                provider=provider_code,
                                old_key_id=current_key.id,
                                new_key_id=next_key.id,
                            )
                            current_key = next_key

                        await asyncio.sleep(delay)

            except AIGatewayError as original_error:
                # 主模型所有重试失败，尝试故障转移
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
                    _("ai.log.fallback_attempt"),
                    original_model=model,
                    fallback_model=fallback_model.code,
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

                    # 更新引用供 on_complete 回调使用
                    api_key = fb_api_key
                    provider = fb_provider
                    ai_model = fallback_model
                    logger.info(
                        _("ai.log.fallback_succeeded"),
                        fallback_model=fallback_model.code,
                    )
                except (AIGatewayError, NotFoundException, BusinessException):
                    logger.warning(
                        _("ai.log.fallback_failed"),
                        fallback_model=fallback_model.code,
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

        # 创建完成回调
        async def on_complete(input_tokens: int, output_tokens: int, total_tokens: int):
            """流式完成回调"""
            if provider and api_key and ai_model:
                # 计算费用和延迟
                cost = CostCalculator.calculate_cost(
                    ai_model, input_tokens, output_tokens
                )
                stream_latency_ms = int((time.time() - start_time) * 1000)

                # 更新 API Key 使用计数并记录使用量（含 TPM/配额校正 + 调用日志）
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

        # 创建 SSE 流式响应
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
        文本嵌入（统一接口，完整调用链路）

        调用链路:
        限流检查 → 配额检查 → 获取 API Key → 调用适配器 → 记录日志 → 更新用量

        Args:
            provider_code: 供应商代码
            texts: 文本列表
            model: 模型名称
            tenant_id: 租户 ID
            user_id: 用户 ID（用于记录使用量）
            **kwargs: 其他参数

        Returns:
            EmbeddingResponse: 嵌入向量响应
        """
        start_time = time.time()

        # 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id

        # 1. 原子检查+记录速率限制 + 配额检查（仅租户调用）
        estimated_input = 0
        if tenant_id:
            estimated_input = TokenCounter.count_messages_tokens(
                [{"role": "user", "content": t} for t in texts]
            )
            await self.usage_recorder.check_rate_and_quota(tenant_id, model_id, ai_model, estimated_input)

        # 3. 调用适配器（含指数退避重试 + API Key 轮换）
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

        # 4. 计算延迟和使用量
        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = response.input_tokens or 0
        total_tokens = response.total_tokens or input_tokens

        cost = CostCalculator.calculate_cost(ai_model, input_tokens, 0) if ai_model else 0

        # 5. 更新 API Key 使用计数（使用实际成功的 Key，重试可能已轮换）
        used_api_key.increment_usage()

        # 6. 记录使用量和日志
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

                # 构建请求数据
                request_data = {
                    "texts": texts[:3],
                    "text_count": len(texts),
                }

                # 异步记录调用日志
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
        图像生成（统一接口，完整调用链路）

        调用链路:
        限流检查 → 配额检查 → 获取 API Key → 调用适配器(含重试) → 记录日志 → 更新用量

        Args:
            provider_code: 供应商代码
            prompt: 生成提示词
            model: 模型名称（如 dall-e-3）
            size: 图片尺寸
            quality: 质量（standard / hd）
            style: 风格（vivid / natural）
            n: 生成数量
            tenant_id: 租户 ID
            user_id: 用户 ID
            **kwargs: 其他参数

        Returns:
            ImageGenerationResponse: 图像生成响应
        """
        start_time = time.time()

        # 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id

        # 原子检查+记录速率限制 + 配额检查（仅租户调用）
        # 生图按固定 token 估算（无法精确预估，使用 1000 作为基准）
        estimated_input = 0
        if tenant_id:
            estimated_input = 1000 * n
            await self.usage_recorder.check_rate_and_quota(
                tenant_id, model_id, ai_model, estimated_input,
            )

        # 调用适配器（含重试）
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

        # 计算延迟
        latency_ms = int((time.time() - start_time) * 1000)

        # 生图无 token 消耗，按次计量
        input_tokens = estimated_input
        output_tokens = 0
        total_tokens = input_tokens

        cost = CostCalculator.calculate_cost(
            ai_model, input_tokens, output_tokens,
        ) if ai_model else 0

        # 更新 API Key 使用计数
        used_api_key.increment_usage()

        # 记录使用量和日志
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
        测试模型连通性和响应质量（不记录日志）

        用于 Admin 端测试模型配置是否正确，不记录调用日志和计量。

        Args:
            provider_id: 供应商 ID
            model_code: 模型代码
            test_prompt: 测试提示词
            stream: 是否使用流式响应
            temperature: 温度参数
            max_tokens: 最大生成 tokens

        Returns:
            TestModelResult: 类型化测试结果
        """
        # 通过 Repository 查询供应商
        provider = await self.provider_repo.get_by_id(provider_id)

        if not provider or not provider.is_active:
            return TestModelResult(
                connected=False,
                error=_("ai.provider_not_found"),
                model=model_code,
            )

        # 通过 Repository 获取平台级 API Key
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

        # 构建测试消息
        messages = [
            ChatMessage(role="user", content=test_prompt),
        ]

        # 记录开始时间
        start_time = time.time()

        try:
            # 创建适配器
            adapter = AdapterRegistry.create_adapter(
                provider_type=provider.type,
                api_key=api_key.decrypt_key(),
                base_url=provider.base_url,
            )

            if stream:
                # 流式响应测试（只取前 5 个 chunk）
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
                # 非流式响应测试
                response = await adapter.chat(
                    messages=messages,
                    model=model_code,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                )

                latency_ms = int((time.time() - start_time) * 1000)

                # 提取响应文本
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
        获取供应商和可用的 API Key

        Args:
            provider_code: 供应商代码
            tenant_id: 租户 ID

        Returns:
            (供应商, API Key) 元组

        Raises:
            NotFoundException: 供应商不存在
            BusinessException: 没有可用的 API Key
        """
        # 通过 Repository 查询供应商
        provider = await self.provider_repo.get_by_code(provider_code)

        if not provider or not provider.is_active:
            raise NotFoundException(message=_("ai.provider_not_found"))

        # 通过 Repository 获取可用 API Key
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
        获取模型信息

        Args:
            model_name: 模型名称
            provider_id: 供应商 ID

        Returns:
            AIModel 实例，如果不存在则返回 None
        """
        return await self.model_repo.get_active_by_name_and_provider(model_name, provider_id)

__all__ = [
    "AIGateway",
]
