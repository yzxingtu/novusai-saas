"""Model test entrypoint helper for the AI gateway facade."""

from __future__ import annotations

import time
from typing import Any

from app.ai.types import ChatMessage, TestModelResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import build_public_error_text
from app.middleware.trace import trace_id_var

logger = LogManager.get_logger("ai")


async def execute_test_model(
    gateway: Any,
    *,
    provider_id: int,
    model_code: str,
    test_prompt: str = "Hello",
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int | None = 500,
    adapter_registry: Any,
) -> TestModelResult:
    """Execute the model test flow for AIGateway.test_model()."""
    provider = await gateway.provider_repo.get_by_id(provider_id)

    if not provider or not provider.is_active:
        return TestModelResult(
            connected=False,
            error=_("ai.provider_not_found"),
            model=model_code,
            trace_id=trace_id_var.get() or None,
        )

    api_key = await gateway.api_key_repo.get_available_key(
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

    ai_model = await gateway._get_model(model_code, provider.id)
    is_embedding = ai_model and ai_model.type == "embedding"

    start_time = time.time()
    effective_request = gateway._resolve_effective_model_request(
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
        adapter = adapter_registry.create_adapter(
            provider_type=provider.type,
            api_key=api_key.decrypt_key(),
            base_url=provider.base_url,
            provider_config=provider.config,
            model_config=getattr(ai_model, "config", None),
        )

        if is_embedding:
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
                effective_reasoning_effort=effective_request.get("reasoning_effort"),
                applied_overrides=list(
                    effective_request.get("applied_overrides", []) or []
                ),
                ignored_overrides=list(
                    effective_request.get("ignored_overrides", []) or []
                ),
                ignore_reasons=dict(effective_request.get("ignore_reasons", {}) or {}),
            )

        messages = [ChatMessage(role="user", content=test_prompt)]

        if stream:
            response_chunks = []
            stream_gen = gateway._stream_chat_adapter(
                adapter=adapter,
                provider=provider,
                messages=messages,
                model=model_code,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=1.0,
                tools=None,
                tool_choice=None,
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
                effective_reasoning_effort=effective_request.get("reasoning_effort"),
                applied_overrides=list(
                    effective_request.get("applied_overrides", []) or []
                ),
                ignored_overrides=list(
                    effective_request.get("ignored_overrides", []) or []
                ),
                ignore_reasons=dict(effective_request.get("ignore_reasons", {}) or {}),
            )

        response = await gateway._call_chat_adapter(
            adapter=adapter,
            provider=provider,
            messages=messages,
            model=model_code,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1.0,
            stream=False,
            tools=None,
            tool_choice=None,
        )

        latency_ms = int((time.time() - start_time) * 1000)
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
            effective_reasoning_effort=effective_request.get("reasoning_effort"),
            applied_overrides=list(
                effective_request.get("applied_overrides", []) or []
            ),
            ignored_overrides=list(effective_request.get("ignored_overrides", []) or []),
            ignore_reasons=dict(effective_request.get("ignore_reasons", {}) or {}),
        )

    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Model test failed: provider={} model={} error={}",
            provider.code,
            model_code,
            str(exc),
        )

        return TestModelResult(
            connected=False,
            latency_ms=latency_ms,
            error=build_public_error_text(
                message=_("ai.request_failed"),
                exc=exc,
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
            ignored_overrides=list(effective_request.get("ignored_overrides", []) or []),
            ignore_reasons=dict(effective_request.get("ignore_reasons", {}) or {}),
        )


__all__ = ["execute_test_model"]
