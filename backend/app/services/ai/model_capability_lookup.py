"""
Model Capability Lookup Service / 模型能力查找服务

Reads the LiteLLM model registry cached in Redis (synced by Celery task)
and provides capability lookup for remote models.
从 Redis 缓存的 LiteLLM 模型注册表中读取数据，为远程模型提供能力查找。
"""

from __future__ import annotations

import json
from typing import Any

from app.core.logging import LogManager
from app.core.redis import get_redis
from app.tasks.scheduled import LITELLM_REDIS_KEY

logger = LogManager.get_logger("ai")

_COMMON_PREFIXES = (
    "openai/",
    "azure/",
    "anthropic/",
    "deepseek/",
    "google/",
    "cohere/",
    "mistral/",
    "groq/",
    "together_ai/",
    "fireworks_ai/",
    "volcengine/",
    "huggingface/",
    "ollama/",
    "bedrock/",
    "dashscope/",
    "siliconflow/",
    "minimax/",
    "kimi/",
)

_PROVIDER_PREFIX_ALIASES: dict[str, tuple[str, ...]] = {
    "anthropic": ("anthropic/",),
    "azure": ("azure/",),
    "bedrock": ("bedrock/",),
    "cohere": ("cohere/",),
    "dashscope": ("dashscope/",),
    "deepseek": ("deepseek/",),
    "fireworks_ai": ("fireworks_ai/",),
    "google": ("google/", "gemini/"),
    "groq": ("groq/",),
    "huggingface": ("huggingface/",),
    "kimi": ("kimi/",),
    "minimax": ("minimax/",),
    "mistral": ("mistral/",),
    "ollama": ("ollama/",),
    "openai": ("openai/",),
    "siliconflow": ("siliconflow/",),
    "together_ai": ("together_ai/",),
    "volcengine": ("volcengine/",),
}


async def get_registry() -> dict[str, Any] | None:
    """
    从 Redis 加载 LiteLLM 注册表 / Load the LiteLLM registry from Redis.
    """
    try:
        redis = await get_redis()
        raw = await redis.get(LITELLM_REDIS_KEY)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.warning("Failed to load LiteLLM registry from Redis: {}", e)
        return None


def _normalize_mode(mode: str | None) -> str | None:
    """Map LiteLLM mode to our model type. / 将 LiteLLM mode 映射为本系统模型类型。"""
    if not mode:
        return None
    mapping = {
        "chat": "chat",
        "completion": "chat",
        "realtime": "chat",
        "embedding": "embedding",
        "image_generation": "image",
    }
    return mapping.get(mode)


def _parse_bool_safe(raw_value: object) -> bool | None:
    """Parse bool safely / 安全解析布尔值。"""
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _parse_int_safe(raw_value: object) -> int | None:
    """Parse int safely / 安全解析整数。"""
    if raw_value is None or raw_value == "":
        return None
    try:
        return int(float(str(raw_value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _collect_modalities(entry: dict[str, Any]) -> set[str]:
    """Collect supported modalities from registry fields / 从注册表字段汇总多模态能力。"""
    values: set[str] = set()
    raw_modalities = entry.get("supported_modalities")
    if isinstance(raw_modalities, list):
        for item in raw_modalities:
            text = str(item).strip().lower()
            if text:
                values.add(text)
    for field, modality in (
        ("supports_audio_input", "audio"),
        ("supports_audio_output", "audio"),
        ("supports_vision", "image"),
        ("supports_video", "video"),
        ("supports_audio", "audio"),
    ):
        parsed = _parse_bool_safe(entry.get(field))
        if parsed:
            values.add(modality)
    return values


def _extract_capabilities(entry: dict[str, Any]) -> dict[str, Any]:
    """Extract capability fields from a LiteLLM registry entry. / 从注册表条目提取能力字段。"""
    caps: dict[str, Any] = {}
    modalities = _collect_modalities(entry)

    supports_vision = _parse_bool_safe(entry.get("supports_vision"))
    if supports_vision is None and "image" in modalities:
        supports_vision = True
    if supports_vision is not None:
        caps["supports_vision"] = supports_vision

    supports_audio = _parse_bool_safe(entry.get("supports_audio"))
    if supports_audio is None and "audio" in modalities:
        supports_audio = True
    if supports_audio is not None:
        caps["supports_audio"] = supports_audio

    supports_video = _parse_bool_safe(entry.get("supports_video"))
    if supports_video is None and "video" in modalities:
        supports_video = True
    if supports_video is not None:
        caps["supports_video"] = supports_video

    supports_function_calling = _parse_bool_safe(
        entry.get("supports_function_calling")
    )
    if supports_function_calling is not None:
        caps["supports_function_calling"] = supports_function_calling

    supports_streaming = _parse_bool_safe(entry.get("supports_streaming"))
    if supports_streaming is None:
        model_type = _normalize_mode(entry.get("mode"))
        if model_type == "chat":
            supports_streaming = True
    if supports_streaming is not None:
        caps["supports_streaming"] = supports_streaming

    context_window = _parse_int_safe(entry.get("context_window"))
    if context_window is None:
        context_window = _parse_int_safe(entry.get("max_input_tokens"))
    if context_window is not None:
        caps["context_window"] = context_window

    max_output_tokens = _parse_int_safe(entry.get("max_output_tokens"))
    if max_output_tokens is not None:
        caps["max_output_tokens"] = max_output_tokens

    model_type = _normalize_mode(entry.get("mode"))
    if model_type:
        caps["model_type"] = model_type

    rpm_limit = _parse_int_safe(entry.get("rpm"))
    if rpm_limit is None:
        rpm_limit = _parse_int_safe(entry.get("rpm_limit"))
    if rpm_limit is not None:
        caps["rpm_limit"] = rpm_limit

    tpm_limit = _parse_int_safe(entry.get("tpm"))
    if tpm_limit is None:
        tpm_limit = _parse_int_safe(entry.get("tpm_limit"))
    if tpm_limit is not None:
        caps["tpm_limit"] = tpm_limit

    input_cost = entry.get("input_cost_per_token")
    if input_cost is not None:
        try:
            caps["input_price_per_1k"] = round(float(input_cost) * 1000, 6)
        except (TypeError, ValueError):
            pass

    output_cost = entry.get("output_cost_per_token")
    if output_cost is not None:
        try:
            caps["output_price_per_1k"] = round(float(output_cost) * 1000, 6)
        except (TypeError, ValueError):
            pass

    return caps


def _get_provider_prefixes(provider_code: str | None) -> tuple[str, ...]:
    """Resolve provider-specific prefixes / 解析供应商专属前缀。"""
    normalized = str(provider_code or "").strip().lower()
    if not normalized:
        return ()
    prefixes = _PROVIDER_PREFIX_ALIASES.get(normalized)
    if prefixes:
        return prefixes
    return (f"{normalized}/",)


def _iter_model_candidates(model_code: str) -> list[str]:
    """Build model alias candidates / 构建模型别名候选。"""
    candidates = [model_code]
    if model_code.endswith("-latest"):
        base_code = model_code[: -len("-latest")]
        if base_code:
            candidates.append(base_code)
    return candidates


def _lookup_by_prefixes(
    registry: dict[str, Any],
    model_code: str,
    prefixes: tuple[str, ...],
) -> dict[str, Any] | None:
    """Try exact and suffix matches under allowed prefixes / 在允许前缀下做精确与后缀匹配。"""
    for prefix in prefixes:
        key = f"{prefix}{model_code}"
        entry = registry.get(key)
        if isinstance(entry, dict):
            return entry

    suffix = f"/{model_code}"
    for key, entry in registry.items():
        if (
            any(key.startswith(prefix) for prefix in prefixes)
            and key.endswith(suffix)
            and isinstance(entry, dict)
        ):
            return entry

    return None


def _lookup_by_suffix_any_provider(
    registry: dict[str, Any],
    model_code: str,
) -> dict[str, Any] | None:
    """Fallback suffix match across all providers / 全供应商后缀兜底匹配。"""
    suffix = f"/{model_code}"
    for key, entry in registry.items():
        if key.endswith(suffix) and isinstance(entry, dict):
            return entry
    return None


def _find_entry(
    registry: dict[str, Any],
    model_code: str,
    provider_code: str | None = None,
) -> dict[str, Any] | None:
    """
    使用多策略匹配查找模型条目 / Find a model entry using multi-strategy matching.

    Strategy order:
    1. Exact match: "gpt-4o"
    2. Provider-aware match when provider_code is known
    3. Generic prefix and suffix match when provider is unknown
    """
    normalized_model_code = str(model_code or "").strip()
    if not normalized_model_code:
        return None

    provider_prefixes = _get_provider_prefixes(provider_code)
    for candidate in _iter_model_candidates(normalized_model_code):
        entry = registry.get(candidate)
        if isinstance(entry, dict):
            return entry

        if provider_prefixes:
            entry = _lookup_by_prefixes(registry, candidate, provider_prefixes)
            if isinstance(entry, dict):
                return entry

        if provider_prefixes:
            continue

        entry = _lookup_by_prefixes(registry, candidate, _COMMON_PREFIXES)
        if isinstance(entry, dict):
            return entry

        entry = _lookup_by_suffix_any_provider(registry, candidate)
        if isinstance(entry, dict):
            return entry

    return None


def _extract_capabilities_from_model(model: Any | None) -> dict[str, Any]:
    """Extract local DB model capability fields. / 从本地模型对象提取能力字段。"""
    if model is None:
        return {}

    caps: dict[str, Any] = {}
    for key in (
        "supports_audio",
        "supports_video",
        "supports_vision",
        "supports_function_calling",
        "supports_streaming",
        "context_window",
        "max_output_tokens",
        "rpm_limit",
        "tpm_limit",
        "input_price_per_1k",
        "output_price_per_1k",
        "type",
    ):
        value = getattr(model, key, None)
        if value is None or value == "":
            continue
        if key == "type":
            caps["model_type"] = value
            continue
        caps[key] = value
    return caps


async def resolve_runtime_model_capabilities(
    *,
    model: Any | None = None,
    model_code: str | None = None,
    provider_code: str | None = None,
) -> dict[str, Any]:
    """
    Resolve merged runtime model capabilities (Redis registry + local model object).
    解析合并后的运行时模型能力（Redis 注册表 + 本地模型对象）。

    Priority / 优先级:
    - Local DB model fields override registry values.
    - 本地 DB 模型字段优先覆盖注册表值。
    """
    effective_model_code = str(
        model_code or getattr(model, "code", "") or ""
    ).strip()
    provider = getattr(model, "provider", None)
    effective_provider_code = str(
        provider_code or getattr(provider, "code", "") or ""
    ).strip() or None

    merged: dict[str, Any] = {}
    remote_caps: dict[str, Any] | None = None
    if effective_model_code:
        remote_caps = await lookup(
            effective_model_code,
            provider_code=effective_provider_code,
        )
        if remote_caps:
            merged.update(remote_caps)

    local_caps = _extract_capabilities_from_model(model)
    if local_caps:
        merged.update(local_caps)

    if remote_caps and local_caps:
        merged["capability_source"] = "registry+local"
    elif local_caps:
        merged["capability_source"] = "local"
    elif remote_caps:
        merged["capability_source"] = "registry"

    if effective_model_code and "model_code" not in merged:
        merged["model_code"] = effective_model_code
    if effective_provider_code and "provider_code" not in merged:
        merged["provider_code"] = effective_provider_code
    return merged


async def lookup(
    model_code: str,
    provider_code: str | None = None,
) -> dict[str, Any] | None:
    """
    查找模型代码对应的能力信息 / Look up capabilities for a model code.

    Returns dict with capability fields, or None if not found.
    """
    registry = await get_registry()
    if not registry:
        return None

    entry = _find_entry(registry, model_code, provider_code=provider_code)
    if not entry:
        return None

    return _extract_capabilities(entry)


async def enrich_remote_models(
    models: list[dict[str, Any]],
    provider_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    批量为远程模型列表附加 LiteLLM 注册表中的能力信息 / Batch enrich remote model list with capabilities from LiteLLM registry.

    Graceful degradation: returns original models if registry is unavailable.
    """
    registry = await get_registry()
    if not registry:
        return models

    enriched = []
    for model in models:
        model_id = model.get("id", "")
        entry = _find_entry(registry, model_id, provider_code=provider_code)
        if entry:
            model = {**model, "capabilities": _extract_capabilities(entry)}
        enriched.append(model)

    return enriched


__all__ = [
    "enrich_remote_models",
    "lookup",
    "resolve_runtime_model_capabilities",
]
