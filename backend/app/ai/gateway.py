"""
AI Gateway Unified Call Interface (Facade) / AI 网关统一调用接口（门面类）

Provides a unified AI call interface, dispatching to corresponding adapters by provider code.
Retry/Key rotation delegated to RetryService; usage/quota/logging delegated to UsageRecorder.
提供统一的 AI 调用接口，内部根据供应商代码分发到对应适配器。
重试/Key 轮换委托 RetryService，使用量/配额/日志委托 UsageRecorder。
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.adapters import AdapterRegistry
from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.cache import AIResponseCache
from app.ai.exceptions import (
    AIGatewayError,
    ProviderConnectionError,
    ProviderTimeoutError,
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
from app.ai.usage_mode import resolve_chat_usage
from app.ai.usage_recorder import UsageRecorder
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
)
from app.configs.service import PLATFORM_TENANT_ID
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.core.runtime_identity import get_runtime_identity_tag
from app.enums.ai import CallStatusEnum, CallTypeEnum, RequestTypeEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.exceptions import BusinessException, NotFoundException
from app.middleware.trace import trace_id_var
from app.models.ai import AIModel, AIProvider, ProviderApiKey
from app.repositories.ai import (
    AIModelRepository,
    AIProviderRepository,
    ProviderApiKeyRepository,
)
from app.services.ai.usage_metrics import CostCalculator, TokenCounter

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
        if user_type:
            return user_type
        if tenant_id is None:
            return None
        if tenant_id == PLATFORM_TENANT_ID:
            return LogUserTypeEnum.ADMIN.value
        return LogUserTypeEnum.TENANT_ADMIN.value

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
        selected_tool_names = [
            ((tool.get("function", {}) or {}).get("name"))
            for tool in (tools or [])
            if isinstance(tool, dict)
        ]
        selected_tool_names = [name for name in selected_tool_names if name]
        request_data: dict[str, object] = {
            "messages": messages_to_dicts(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "tools": tools,
            "tool_choice": tool_choice,
            "runtime_identity": get_runtime_identity_tag(),
            "selected_tool_names": selected_tool_names,
            "all_tool_names": all_tool_names or selected_tool_names,
            "tool_use_policy": {
                "family": tool_use_policy_family or "none",
                "mode": tool_use_policy_mode or ("auto" if tools else "none"),
                "allowed_tool_names": allowed_tool_names or [],
            },
        }
        if stream:
            request_data["_stream"] = True
        if retry_count > 0:
            request_data["_retry_count"] = retry_count
        if breach_retry_result:
            request_data["breach_retry_result"] = breach_retry_result
        return request_data

    @staticmethod
    def _warn_policy_not_loaded(
        *,
        tools: list[dict] | None,
        tool_choice: str | None,
        conversation_id: int | None,
        agent_id: int | None,
    ) -> None:
        if not tools:
            return
        tool_names = {
            (tool.get("function", {}) or {}).get("name", "")
            for tool in tools
            if isinstance(tool, dict)
        }
        if not ({"web_search", "fetch_url"} & tool_names):
            return
        if tool_choice:
            return
        logger.warning(
            "Tool policy not loaded: status=policy_not_loaded runtime={} conversation_id={} agent_id={} tool_names={}",
            get_runtime_identity_tag(),
            conversation_id,
            agent_id,
            sorted(name for name in tool_names if name),
        )

    @staticmethod
    def _resolve_billing_context(
        tenant_id: int | None,
        *,
        user_id: int | None,
        user_type: str | None,
        billing_context: dict | None = None,
    ) -> dict[str, object | None]:
        """
        Resolve immutable billing attribution defaults for call logging.
        解析调用日志的不可变计费归属默认值。
        """
        resolved = dict(billing_context or {})
        default_billing_tenant_id = (
            tenant_id
            if tenant_id is not None and tenant_id > PLATFORM_TENANT_ID
            else None
        )
        resolved.setdefault("billing_tenant_id", default_billing_tenant_id)
        resolved.setdefault("actor_user_id", user_id)
        resolved.setdefault("actor_user_type", user_type)
        return resolved

    @staticmethod
    def _merge_model_provider_snapshots(
        billing_context: dict | None,
        *,
        provider: AIProvider | None,
        ai_model: AIModel | None,
    ) -> dict[str, object | None]:
        """Attach model/provider display snapshots for immutable call ledger rows."""
        merged = dict(billing_context or {})
        if ai_model is not None:
            merged.setdefault(
                "model_name_snapshot",
                getattr(ai_model, "name", None) or getattr(ai_model, "code", None),
            )
        if provider is not None:
            merged.setdefault(
                "provider_name_snapshot",
                getattr(provider, "name", None) or getattr(provider, "code", None),
            )
        return merged

    @staticmethod
    def _attach_runtime_metadata(
        payload: ChatResponse | EmbeddingResponse | ImageGenerationResponse,
        *,
        provider: AIProvider,
        ai_model: AIModel,
    ) -> None:
        """Attach actual runtime provider/model snapshot to response metadata."""
        metadata = dict(getattr(payload, "metadata", {}) or {})
        metadata["runtime_model_info"] = {
            "provider_id": provider.id,
            "provider_name": (
                getattr(provider, "name", None)
                or getattr(provider, "code", None)
                or f"Provider #{provider.id}"
            ),
            "model_id": ai_model.id,
            "model_name": (
                getattr(ai_model, "name", None)
                or getattr(ai_model, "code", None)
                or f"Model #{ai_model.id}"
            ),
            "model_code": getattr(ai_model, "code", None),
        }
        payload.metadata = metadata

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
    def _raise_retryable_native_web_search_failure(
        run: SearchProviderRun,
        *,
        provider_code: str,
        model_code: str,
    ) -> SearchProviderRun:
        if run.status == STATUS_TIMEOUT:
            raise ProviderTimeoutError(
                message=run.failure_reason or _("ai.error.provider_timeout"),
                provider_code=provider_code,
                model_code=model_code,
            )
        if run.status == STATUS_UPSTREAM_ERROR:
            raise ProviderConnectionError(
                message=run.failure_reason or _("ai.error.provider_connection"),
                provider_code=provider_code,
                model_code=model_code,
            )
        return run

    @staticmethod
    def _native_web_search_error_status(error: Exception) -> str:
        if isinstance(error, ProviderTimeoutError):
            return STATUS_TIMEOUT
        return STATUS_UPSTREAM_ERROR

    @staticmethod
    def _native_web_search_call_status(status: str) -> str:
        if status == STATUS_TIMEOUT:
            return CallStatusEnum.TIMEOUT.value
        if status in {STATUS_UPSTREAM_ERROR, STATUS_UNSUPPORTED}:
            return CallStatusEnum.FAILED.value
        return CallStatusEnum.SUCCESS.value

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
        start_time = time.time()
        request_messages = [ChatMessage(role="user", content=query)]
        effective_backend_key = (
            str(backend_key or "").strip()
            or f"native:{str(provider_label or provider_code or 'provider').strip() or 'provider'}:{model}"
        )
        effective_provider_label = str(provider_label or provider_code or "").strip() or None

        try:
            provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        except NotFoundException:
            return SearchProviderRun(
                provider=effective_provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="runtime provider unavailable",
                latency_ms=int((time.time() - start_time) * 1000),
                attempted_backends=[effective_backend_key],
                native_attempted=False,
            )
        except BusinessException as exc:
            return SearchProviderRun(
                provider=effective_provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_UPSTREAM_ERROR,
                items=[],
                failure_reason=str(exc),
                latency_ms=int((time.time() - start_time) * 1000),
                attempted_backends=[effective_backend_key],
                native_attempted=False,
            )

        ai_model = await self._get_model(model, provider.id)
        if not ai_model:
            return SearchProviderRun(
                provider=effective_provider_label
                or str(getattr(provider, "code", "") or provider.type or "").strip()
                or None,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="runtime model unavailable",
                latency_ms=int((time.time() - start_time) * 1000),
                attempted_backends=[effective_backend_key],
                native_attempted=False,
            )

        effective_provider_label = (
            effective_provider_label
            or str(getattr(provider, "code", "") or provider.type or "").strip()
        )
        adapter_class = AdapterRegistry.get_adapter(provider.type)
        if adapter_class is None:
            return SearchProviderRun(
                provider=effective_provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason=f"adapter not registered for provider type {provider.type}",
                latency_ms=int((time.time() - start_time) * 1000),
                attempted_backends=[effective_backend_key],
                native_attempted=False,
            )

        preflight_adapter = AdapterRegistry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
            provider_config=provider.config,
            **self._build_adapter_extra(
                ai_model=ai_model,
                tenant_id=tenant_id,
            ),
        )
        if not preflight_adapter.supports_native_web_search(model):
            return SearchProviderRun(
                provider=effective_provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="adapter/model does not expose native web search",
                latency_ms=int((time.time() - start_time) * 1000),
                attempted_backends=[effective_backend_key],
                native_attempted=False,
            )

        should_meter_usage = self._should_meter_usage(tenant_id)
        should_record_call_log = self._should_record_call_log(tenant_id)
        call_user_type = self._resolve_call_user_type(tenant_id, user_type)
        resolved_billing_context = self._resolve_billing_context(
            tenant_id,
            user_id=user_id,
            user_type=call_user_type,
            billing_context=billing_context,
        )
        request_data = self._build_request_log_data(
            messages=request_messages,
            temperature=0.0,
            max_tokens=None,
            top_p=1.0,
            tools=[{"type": "function", "function": {"name": "web_search"}}],
            tool_choice="required",
            all_tool_names=["web_search", "fetch_url"],
            tool_use_policy_family="web_research",
            tool_use_policy_mode="required",
            allowed_tool_names=["web_search", "fetch_url"],
        )
        request_data.update(
            {
                "query": query,
                "max_results": max_results,
                "locale": locale,
                "timeout_seconds": timeout_seconds,
                "provider_mode": PROVIDER_MODE_NATIVE,
                "backend_key": effective_backend_key,
            }
        )

        estimated_input = 0
        metering_context = None
        if should_meter_usage or should_record_call_log:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(request_messages)
            )
        if should_meter_usage:
            metering_context = await self.usage_recorder.check_rate_and_quota(
                tenant_id,
                ai_model.id,
                ai_model,
                estimated_input,
            )

        async def _run_native_search_with_retry(adapter: Any) -> SearchProviderRun:
            run = await adapter.native_web_search(
                query=query,
                max_results=max_results,
                locale=locale,
                timeout_seconds=timeout_seconds,
                model=model,
                provider_label=effective_provider_label,
                backend_key=effective_backend_key,
            )
            return self._raise_retryable_native_web_search_failure(
                run,
                provider_code=provider.code,
                model_code=model,
            )

        try:
            run, retry_count, used_api_key = await self.retry_service.execute_with_retry(
                provider=provider,
                api_key=api_key,
                model=model,
                call_fn=_run_native_search_with_retry,
                tenant_id=tenant_id,
                log_key="ai.log.gateway_native_web_search_call",
                adapter_extra={
                    **self._build_adapter_extra(
                        ai_model=ai_model,
                        tenant_id=tenant_id,
                    ),
                },
            )
        except AIGatewayError as exc:
            latency_ms = int((time.time() - start_time) * 1000)
            failure_status = self._native_web_search_error_status(exc)
            if should_record_call_log:
                try:
                    assert tenant_id is not None
                    await self.usage_recorder.call_log_service.log_call_async(
                        tenant_id=tenant_id,
                        model_id=ai_model.id,
                        provider_id=provider.id,
                        request_type=RequestTypeEnum.CHAT.value,
                        request_data=request_data,
                        response_data={
                            "status": failure_status,
                            "provider_mode": PROVIDER_MODE_NATIVE,
                            "backend_key": effective_backend_key,
                            "result_count": 0,
                            "_retry_count": MAX_RETRIES,
                        },
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        cost=0,
                        latency_ms=latency_ms,
                        status=self._native_web_search_call_status(failure_status),
                        error_message=str(exc),
                        user_id=user_id,
                        user_type=call_user_type,
                        agent_id=agent_id,
                        conversation_id=conversation_id,
                        billing_context=self._merge_model_provider_snapshots(
                            resolved_billing_context,
                            provider=provider,
                            ai_model=ai_model,
                        ),
                        call_type=call_type,
                    )
                except Exception as log_exc:  # noqa: BLE001
                    logger.error("AI call log enqueue failed: {}", str(log_exc))

            return SearchProviderRun(
                provider=effective_provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=effective_backend_key,
                status=failure_status,
                items=[],
                failure_reason=str(exc),
                latency_ms=latency_ms,
                attempted_backends=[effective_backend_key],
                native_attempted=True,
            )

        run.provider = run.provider or effective_provider_label
        run.provider_mode = run.provider_mode or PROVIDER_MODE_NATIVE
        run.backend_key = run.backend_key or effective_backend_key
        run.attempted_backends = list(run.attempted_backends or [effective_backend_key])
        run.latency_ms = int((time.time() - start_time) * 1000)
        run.native_attempted = True

        cost = CostCalculator.calculate_cost(
            ai_model,
            run.input_tokens,
            run.output_tokens,
        )
        if should_meter_usage:
            assert tenant_id is not None
            await self.usage_recorder.record_usage_and_adjust(
                tenant_id=tenant_id,
                model_id=ai_model.id,
                request_type=RequestTypeEnum.CHAT.value,
                input_tokens=run.input_tokens,
                output_tokens=run.output_tokens,
                total_tokens=run.total_tokens,
                cost=cost,
                estimated_input=estimated_input,
                latency_ms=run.latency_ms,
                user_id=user_id,
                metering_context=metering_context,
            )

        used_api_key.increment_usage()

        if should_record_call_log:
            try:
                assert tenant_id is not None
                response_data = {
                    "status": run.status,
                    "provider_mode": run.provider_mode,
                    "backend_key": run.backend_key,
                    "result_count": len(run.items),
                    "items": [item.to_summary_item() for item in run.items[:max_results]],
                    "_retry_count": retry_count,
                }
                if run.failure_reason:
                    response_data["failure_reason"] = run.failure_reason
                await self.usage_recorder.call_log_service.log_call_async(
                    tenant_id=tenant_id,
                    model_id=ai_model.id,
                    provider_id=provider.id,
                    request_type=RequestTypeEnum.CHAT.value,
                    request_data=request_data,
                    response_data=response_data,
                    input_tokens=run.input_tokens,
                    output_tokens=run.output_tokens,
                    total_tokens=run.total_tokens,
                    cost=cost,
                    latency_ms=run.latency_ms,
                    status=self._native_web_search_call_status(run.status),
                    user_id=user_id,
                    user_type=call_user_type,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=self._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    call_type=call_type,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("AI call log enqueue failed: {}", str(exc))

        await self.db.commit()
        return run

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
        start_time = time.time()

        # Get provider, API Key, and model info / 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id
        should_meter_usage = self._should_meter_usage(tenant_id)
        should_record_call_log = self._should_record_call_log(tenant_id)
        call_user_type = self._resolve_call_user_type(tenant_id, user_type)
        resolved_billing_context = self._resolve_billing_context(
            tenant_id,
            user_id=user_id,
            user_type=call_user_type,
            billing_context=billing_context,
        )

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
                tool_choice=tool_choice,
            )

            cached_response = await AIResponseCache.get(cache_key)
            if cached_response:
                logger.info("Cache hit: key={}", cache_key)
                api_key.mark_last_used()
                await self.db.flush()
                return ChatResponse(**cached_response)

        # 2. Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 检查配额（仅企业调用）
        estimated_input = 0
        metering_context = None
        if should_meter_usage or should_record_call_log:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
        if should_meter_usage:
            metering_context = await self.usage_recorder.check_rate_and_quota(
                tenant_id,
                model_id,
                ai_model,
                estimated_input,
            )

        # 4. Call adapter (with exponential backoff retry + failover) / 调用适配器（含指数退避重试 + 故障转移）
        self._warn_policy_not_loaded(
            tools=tools,
            tool_choice=tool_choice,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )
        try:
            (
                response,
                retry_count,
                used_api_key,
            ) = await self.retry_service.execute_with_retry(
                provider=provider,
                api_key=api_key,
                model=model,
                call_fn=lambda adapter: adapter.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stream=stream,
                    tools=tools,
                    tool_choice=tool_choice,
                    **kwargs,
                ),
                tenant_id=tenant_id,
                adapter_extra={
                    **self._build_adapter_extra(
                        ai_model=ai_model,
                        tenant_id=tenant_id,
                    ),
                },
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
                    tool_choice=tool_choice,
                    selected_tool_names=[
                        ((tool.get("function", {}) or {}).get("name"))
                        for tool in (tools or [])
                        if isinstance(tool, dict)
                    ],
                    all_tool_names=all_tool_names,
                    tool_use_policy_family=tool_use_policy_family,
                    tool_use_policy_mode=tool_use_policy_mode,
                    allowed_tool_names=allowed_tool_names,
                    breach_retry_result=breach_retry_result,
                    request_type=RequestTypeEnum.CHAT.value,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_type=call_user_type,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=self._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                    call_type=call_type,
                )
                raise

            logger.info(
                "Fallback attempt: original_model={} fallback_model={}",
                model,
                fallback_model.code,
            )

            try:
                fb_provider, fb_api_key = await self.get_provider_and_key(
                    fallback_model.provider.code, tenant_id
                )
                (
                    response,
                    retry_count,
                    used_api_key,
                ) = await self.retry_service.execute_with_retry(
                    provider=fb_provider,
                    api_key=fb_api_key,
                    model=fallback_model.code,
                    call_fn=lambda adapter: adapter.chat(
                        messages=messages,
                        model=fallback_model.code,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        stream=stream,
                        tools=tools,
                        tool_choice=tool_choice,
                        **kwargs,
                    ),
                    tenant_id=tenant_id,
                    adapter_extra={
                        **self._build_adapter_extra(
                            ai_model=fallback_model,
                            tenant_id=tenant_id,
                        ),
                    },
                )
                # Update references for subsequent metering / 更新引用用于后续计量
                provider = fb_provider
                api_key = fb_api_key
                ai_model = fallback_model
                model_id = fallback_model.id
                model = fallback_model.code
                logger.info(
                    "Fallback succeeded: fallback_model={}",
                    fallback_model.code,
                )
            except (AIGatewayError, NotFoundException, BusinessException):
                logger.warning(
                    "Fallback failed: fallback_model={}",
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
                    tool_choice=tool_choice,
                    selected_tool_names=[
                        ((tool.get("function", {}) or {}).get("name"))
                        for tool in (tools or [])
                        if isinstance(tool, dict)
                    ],
                    all_tool_names=all_tool_names,
                    tool_use_policy_family=tool_use_policy_family,
                    tool_use_policy_mode=tool_use_policy_mode,
                    allowed_tool_names=allowed_tool_names,
                    breach_retry_result=breach_retry_result,
                    request_type=RequestTypeEnum.CHAT.value,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user_type=call_user_type,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=self._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                    call_type=call_type,
                )
                raise original_error from None

        # 5. Calculate latency and usage / 计算延迟和使用量
        latency_ms = int((time.time() - start_time) * 1000)

        usage = resolve_chat_usage(
            messages=messages,
            output_text=response.message.content or "",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            estimated_input=estimated_input,
        )
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        total_tokens = usage.total_tokens

        cost = (
            CostCalculator.calculate_cost(ai_model, input_tokens, output_tokens)
            if ai_model
            else 0
        )
        self._attach_runtime_metadata(response, provider=provider, ai_model=ai_model)
        response.metadata["usage_mode"] = usage.usage_mode

        # 6–7. 先租户计量（失败则整请求回滚，不增加 Key），再 Key 计数；Celery 日志单独 best-effort
        if should_meter_usage:
            assert tenant_id is not None
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
                metering_context=metering_context,
            )

        used_api_key.increment_usage()

        if should_record_call_log:
            try:
                assert tenant_id is not None
                request_data = self._build_request_log_data(
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
                )

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
                    user_type=call_user_type,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=self._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                    call_type=call_type,
                )
            except Exception as e:
                logger.error("AI call log enqueue failed: {}", str(e))

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
                logger.error("Cache set failed: {}", str(e))

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
        start_time = time.time()

        # Get provider, API Key, and model info (before creating generator) / 获取供应商、API Key 和模型信息（在创建生成器之前）
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))
        should_meter_usage = self._should_meter_usage(tenant_id)
        call_user_type = self._resolve_call_user_type(tenant_id, user_type)
        resolved_billing_context = self._resolve_billing_context(
            tenant_id,
            user_id=user_id,
            user_type=call_user_type,
            billing_context=billing_context,
        )

        # Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 配额检查（仅企业调用）
        estimated_input = 0
        metering_context = None
        if should_meter_usage:
            estimated_input = TokenCounter.count_messages_tokens(
                messages_to_dicts(messages)
            )
            metering_context = await self.usage_recorder.check_rate_and_quota(
                tenant_id,
                ai_model.id,
                ai_model,
                estimated_input,
            )
        self._warn_policy_not_loaded(
            tools=tools,
            tool_choice=tool_choice,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )

        async def generate_chunks() -> AsyncIterator[ChatChunk]:
            """Internal async generator using pre-fetched provider, api_key, ai_model. / 内部异步生成器，使用已获取的 provider, api_key, ai_model。

            With exponential backoff retry, API Key rotation, and failover.
            带指数退避重试、API Key 轮换和故障转移。
            """
            nonlocal api_key, provider, ai_model, model
            current_key = api_key

            try:
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        # Create adapter instance / 创建适配器实例
                        adapter = AdapterRegistry.create_adapter(
                            provider_type=provider.type,
                            api_key=current_key.decrypt_key(),
                            base_url=provider.base_url,
                            provider_config=provider.config,
                            internal_db=self.db,
                            internal_tenant_id=tenant_id,
                            model_config=getattr(ai_model, "config", None),
                        )

                        # Call adapter streaming interface / 调用适配器流式接口
                        logger.info(
                            "Gateway stream call: provider={} model={}",
                            provider_code,
                            model,
                        )

                        async for chunk in adapter.stream_chat(
                            messages=messages,
                            model=model,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            top_p=top_p,
                            tools=tools,
                            tool_choice=tool_choice,
                            **kwargs,
                        ):
                            yield chunk

                        # Log on retry success / 重试成功时记录日志
                        if attempt > 0:
                            logger.info(
                                "Stream retry succeeded: provider={} model={} attempt={}",
                                provider_code,
                                model,
                                attempt,
                            )

                        # Update outer api_key reference / 更新外层 api_key 引用
                        api_key = current_key
                        return  # Streaming completed successfully / 流式传输成功完成

                    except AIGatewayError as e:
                        # Non-retryable exception, raise immediately / 不可重试的异常直接抛出
                        if not is_retryable(e):
                            logger.error(
                                "Non-retryable error: provider={} model={} error_code={} error={}",
                                provider_code,
                                model,
                                e.error_code,
                                str(e),
                            )
                            raise

                        # Max retries exhausted / 已达最大重试次数
                        if attempt >= MAX_RETRIES:
                            logger.error(
                                "Max retries exhausted: provider={} model={} attempts={} error={}",
                                provider_code,
                                model,
                                attempt + 1,
                                str(e),
                            )
                            raise

                        # Calculate backoff delay / 计算退避延迟
                        delay = RETRY_BASE_DELAY * (RETRY_MULTIPLIER**attempt)
                        if e.retry_after and e.retry_after > delay:
                            delay = float(e.retry_after)

                        logger.warning(
                            "Retrying after error: provider={} model={} attempt={} delay={}s error_code={} error={}",
                            provider_code,
                            model,
                            attempt,
                            delay,
                            e.error_code,
                            str(e),
                        )

                        # Try switching API Key / 尝试切换 API Key
                        next_key = await self.retry_service.get_next_api_key(
                            provider_id=provider.id,
                            current_key_id=current_key.id,
                            tenant_id=tenant_id,
                        )
                        if next_key:
                            logger.info(
                                "Switching API key: provider={} old_key={} new_key={}",
                                provider_code,
                                current_key.id,
                                next_key.id,
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
                        tool_choice=tool_choice,
                        selected_tool_names=[
                            ((tool.get("function", {}) or {}).get("name"))
                            for tool in (tools or [])
                            if isinstance(tool, dict)
                        ],
                        all_tool_names=all_tool_names,
                        tool_use_policy_family=tool_use_policy_family,
                        tool_use_policy_mode=tool_use_policy_mode,
                        allowed_tool_names=allowed_tool_names,
                        breach_retry_result=breach_retry_result,
                        request_type=RequestTypeEnum.CHAT.value,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        user_type=call_user_type,
                        agent_id=agent_id,
                        conversation_id=conversation_id,
                        billing_context=self._merge_model_provider_snapshots(
                            resolved_billing_context,
                            provider=provider,
                            ai_model=ai_model,
                        ),
                        routed_model_id=routed_model_id,
                        route_reason=route_reason,
                    )
                    raise

                logger.info(
                    "Fallback attempt: original_model={} fallback_model={}",
                    model,
                    fallback_model.code,
                )

                try:
                    fb_provider, fb_api_key = await self.get_provider_and_key(
                        fallback_model.provider.code, tenant_id
                    )
                    fb_adapter = AdapterRegistry.create_adapter(
                        provider_type=fb_provider.type,
                        api_key=fb_api_key.decrypt_key(),
                        base_url=fb_provider.base_url,
                        provider_config=fb_provider.config,
                        internal_db=self.db,
                        internal_tenant_id=tenant_id,
                        model_config=getattr(fallback_model, "config", None),
                    )

                    async for chunk in fb_adapter.stream_chat(
                        messages=messages,
                        model=fallback_model.code,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        tools=tools,
                        tool_choice=tool_choice,
                        **kwargs,
                    ):
                        yield chunk

                    # Update references for on_complete callback / 更新引用供 on_complete 回调使用
                    api_key = fb_api_key
                    provider = fb_provider
                    ai_model = fallback_model
                    model = fallback_model.code
                    logger.info(
                        "Fallback succeeded: fallback_model={}",
                        fallback_model.code,
                    )
                except (AIGatewayError, NotFoundException, BusinessException):
                    logger.warning(
                        "Fallback failed: fallback_model={}",
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
                        tool_choice=tool_choice,
                        selected_tool_names=[
                            ((tool.get("function", {}) or {}).get("name"))
                            for tool in (tools or [])
                            if isinstance(tool, dict)
                        ],
                        all_tool_names=all_tool_names,
                        tool_use_policy_family=tool_use_policy_family,
                        tool_use_policy_mode=tool_use_policy_mode,
                        allowed_tool_names=allowed_tool_names,
                        breach_retry_result=breach_retry_result,
                        request_type=RequestTypeEnum.CHAT.value,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        user_type=call_user_type,
                        agent_id=agent_id,
                        conversation_id=conversation_id,
                        billing_context=self._merge_model_provider_snapshots(
                            resolved_billing_context,
                            provider=provider,
                            ai_model=ai_model,
                        ),
                        routed_model_id=routed_model_id,
                        route_reason=route_reason,
                    )
                    raise original_error from None

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
                    user_type=call_user_type,
                    model_id=ai_model.id,
                    estimated_input=estimated_input,
                    latency_ms=stream_latency_ms,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=self._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    routed_model_id=routed_model_id,
                    route_reason=route_reason,
                    metering_context=metering_context,
                    call_type=call_type,
                    request_data=self._build_request_log_data(
                        messages=messages,
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
                        stream=True,
                    ),
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
        start_time = time.time()

        # Get provider, API Key, and model info / 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id
        should_meter_usage = self._should_meter_usage(tenant_id)
        should_record_call_log = self._should_record_call_log(tenant_id)
        call_user_type = self._resolve_call_user_type(tenant_id, user_type)
        resolved_billing_context = self._resolve_billing_context(
            tenant_id,
            user_id=user_id,
            user_type=call_user_type,
            billing_context=billing_context,
        )

        # 1. Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 配额检查（仅企业调用）
        estimated_input = 0
        metering_context = None
        if should_meter_usage:
            estimated_input = TokenCounter.count_messages_tokens(
                [{"role": "user", "content": t} for t in texts]
            )
            metering_context = await self.usage_recorder.check_rate_and_quota(
                tenant_id,
                model_id,
                ai_model,
                estimated_input,
            )

        # 3. Call adapter (with exponential backoff retry + API Key rotation) / 调用适配器（含指数退避重试 + API Key 轮换）
        (
            response,
            _retry_count,
            used_api_key,
        ) = await self.retry_service.execute_with_retry(
            provider=provider,
            api_key=api_key,
            model=model,
            call_fn=lambda adapter: adapter.embedding(
                texts=texts,
                model=model,
                **kwargs,
            ),
            tenant_id=tenant_id,
            log_key="ai.log.gateway_embedding_call",
            adapter_extra={
                **self._build_adapter_extra(
                    ai_model=ai_model,
                    tenant_id=tenant_id,
                ),
            },
        )
        self._attach_runtime_metadata(response, provider=provider, ai_model=ai_model)

        # 4. Calculate latency and usage / 计算延迟和使用量
        latency_ms = int((time.time() - start_time) * 1000)

        input_tokens = response.input_tokens or 0
        total_tokens = response.total_tokens or input_tokens

        cost = (
            CostCalculator.calculate_cost(ai_model, input_tokens, 0) if ai_model else 0
        )

        if should_meter_usage:
            assert tenant_id is not None
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
                metering_context=metering_context,
            )

        used_api_key.increment_usage()

        if should_record_call_log:
            try:
                assert tenant_id is not None
                request_data = {
                    "texts": texts[:3],
                    "text_count": len(texts),
                }

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
                    user_type=call_user_type,
                    billing_context=self._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    call_type=call_type,
                )
            except Exception as e:
                logger.error("AI call log enqueue failed: {}", str(e))

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
        start_time = time.time()

        # Get provider, API Key, and model info / 获取供应商、API Key 和模型信息
        provider, api_key = await self.get_provider_and_key(provider_code, tenant_id)
        ai_model = await self._get_model(model, provider.id)

        if not ai_model:
            raise NotFoundException(message=_("ai.error.model_not_found"))

        model_id = ai_model.id
        should_meter_usage = self._should_meter_usage(tenant_id)
        should_record_call_log = self._should_record_call_log(tenant_id)
        call_user_type = self._resolve_call_user_type(tenant_id, user_type)
        resolved_billing_context = self._resolve_billing_context(
            tenant_id,
            user_id=user_id,
            user_type=call_user_type,
            billing_context=billing_context,
        )

        # Atomic check+record rate limit + quota check (tenant calls only) / 原子检查+记录速率限制 + 配额检查（仅企业调用）
        # Image generation uses fixed token estimate (cannot predict precisely, use 1000 as baseline) / 生图按固定 token 估算（无法精确预估，使用 1000 作为基准）
        estimated_input = 0
        metering_context = None
        if should_meter_usage:
            estimated_input = 1000 * n
            metering_context = await self.usage_recorder.check_rate_and_quota(
                tenant_id,
                model_id,
                ai_model,
                estimated_input,
            )

        # Call adapter (with retry) / 调用适配器（含重试）
        (
            response,
            _retry_count,
            used_api_key,
        ) = await self.retry_service.execute_with_retry(
            provider=provider,
            api_key=api_key,
            model=model,
            call_fn=lambda adapter: adapter.generate_image(
                prompt=prompt,
                model=model,
                size=size,
                quality=quality,
                style=style,
                n=n,
                **kwargs,
            ),
            tenant_id=tenant_id,
            log_key="ai.log.gateway_image_call",
            adapter_extra={
                **self._build_adapter_extra(
                    ai_model=ai_model,
                    tenant_id=tenant_id,
                ),
            },
        )
        self._attach_runtime_metadata(response, provider=provider, ai_model=ai_model)

        # Calculate latency / 计算延迟
        latency_ms = int((time.time() - start_time) * 1000)

        # No token consumption for image generation, metered per request / 生图无 token 消耗，按次计量
        input_tokens = estimated_input
        output_tokens = 0
        total_tokens = input_tokens

        cost = (
            CostCalculator.calculate_cost(
                ai_model,
                input_tokens,
                output_tokens,
            )
            if ai_model
            else 0
        )

        if should_meter_usage:
            assert tenant_id is not None
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
                metering_context=metering_context,
            )

        used_api_key.increment_usage()

        if should_record_call_log:
            try:
                assert tenant_id is not None
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
                    user_type=call_user_type,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    billing_context=self._merge_model_provider_snapshots(
                        resolved_billing_context,
                        provider=provider,
                        ai_model=ai_model,
                    ),
                    call_type=call_type,
                )
            except Exception as e:
                logger.error("AI call log enqueue failed: {}", str(e))

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
                trace_id=trace_id_var.get() or None,
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
                trace_id=trace_id_var.get() or None,
                wire_api=(
                    (provider.config or {}).get("wire_api", "chat_completions")
                    if isinstance(provider.config, dict)
                    else "chat_completions"
                ),
            )

        # Detect model type (embedding models need different test approach) / 检测模型类型（embedding 模型需要不同的测试方式）
        ai_model = await self._get_model(model_code, provider.id)
        is_embedding = ai_model and ai_model.type == "embedding"

        # Record start time / 记录开始时间
        start_time = time.time()
        effective_request = self._resolve_effective_model_request(
            provider=provider,
            ai_model=ai_model,
            model_code=model_code,
            wire_api=(
                (provider.config or {}).get("wire_api")
                if isinstance(provider.config, dict)
                else None
            ),
        )
        trace_id = trace_id_var.get() or None

        try:
            logger.info(
                "AI model test config: provider={} provider_id={} logical_model_code={} effective_upstream_model={} effective_reasoning_effort={} base_url={} wire_api={} api_key_id={} stream={}",
                provider.code,
                provider.id,
                model_code,
                effective_request["upstream_model"],
                effective_request.get("reasoning_effort") or "",
                provider.base_url or "",
                (provider.config or {}).get("wire_api", "chat_completions")
                if isinstance(provider.config, dict)
                else "chat_completions",
                api_key.id,
                stream,
            )
            # Create adapter / 创建适配器
            adapter = AdapterRegistry.create_adapter(
                provider_type=provider.type,
                api_key=api_key.decrypt_key(),
                base_url=provider.base_url,
                provider_config=provider.config,
                model_config=getattr(ai_model, "config", None),
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
                    trace_id=trace_id,
                    wire_api=(
                        (provider.config or {}).get("wire_api", "chat_completions")
                        if isinstance(provider.config, dict)
                        else "chat_completions"
                    ),
                    effective_upstream_model=effective_request["upstream_model"],
                    effective_reasoning_effort=effective_request.get(
                        "reasoning_effort"
                    ),
                    applied_overrides=list(
                        effective_request.get("applied_overrides", []) or []
                    ),
                    ignored_overrides=list(
                        effective_request.get("ignored_overrides", []) or []
                    ),
                    ignore_reasons=dict(
                        effective_request.get("ignore_reasons", {}) or {}
                    ),
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
                    trace_id=trace_id,
                    wire_api=(
                        (provider.config or {}).get("wire_api", "chat_completions")
                        if isinstance(provider.config, dict)
                        else "chat_completions"
                    ),
                    effective_upstream_model=effective_request["upstream_model"],
                    effective_reasoning_effort=effective_request.get(
                        "reasoning_effort"
                    ),
                    applied_overrides=list(
                        effective_request.get("applied_overrides", []) or []
                    ),
                    ignored_overrides=list(
                        effective_request.get("ignored_overrides", []) or []
                    ),
                    ignore_reasons=dict(
                        effective_request.get("ignore_reasons", {}) or {}
                    ),
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
                    trace_id=trace_id,
                    wire_api=(
                        (provider.config or {}).get("wire_api", "chat_completions")
                        if isinstance(provider.config, dict)
                        else "chat_completions"
                    ),
                    effective_upstream_model=effective_request["upstream_model"],
                    effective_reasoning_effort=effective_request.get(
                        "reasoning_effort"
                    ),
                    applied_overrides=list(
                        effective_request.get("applied_overrides", []) or []
                    ),
                    ignored_overrides=list(
                        effective_request.get("ignored_overrides", []) or []
                    ),
                    ignore_reasons=dict(
                        effective_request.get("ignore_reasons", {}) or {}
                    ),
                )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "Model test failed: provider={} model={} error={}",
                provider.code,
                model_code,
                str(e),
            )

            return TestModelResult(
                connected=False,
                latency_ms=latency_ms,
                error=build_public_error_text(
                    message=_("ai.request_failed"),
                    exc=e,
                ),
                model=model_code,
                provider=provider.code,
                trace_id=trace_id,
                wire_api=(
                    (provider.config or {}).get("wire_api", "chat_completions")
                    if isinstance(provider.config, dict)
                    else "chat_completions"
                ),
                effective_upstream_model=effective_request["upstream_model"],
                effective_reasoning_effort=effective_request.get("reasoning_effort"),
                applied_overrides=list(
                    effective_request.get("applied_overrides", []) or []
                ),
                ignored_overrides=list(
                    effective_request.get("ignored_overrides", []) or []
                ),
                ignore_reasons=dict(effective_request.get("ignore_reasons", {}) or {}),
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
