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
        logger.warning("Failed to load LiteLLM registry from Redis: %s", e)
        return None


def _normalize_mode(mode: str | None) -> str | None:
    """Map LiteLLM mode to our model type. / 将 LiteLLM mode 映射为本系统模型类型。"""
    if not mode:
        return None
    mapping = {
        "chat": "chat",
        "completion": "chat",
        "embedding": "embedding",
        "image_generation": "image",
    }
    return mapping.get(mode)


def _extract_capabilities(entry: dict[str, Any]) -> dict[str, Any]:
    """Extract capability fields from a LiteLLM registry entry. / 从注册表条目提取能力字段。"""
    caps: dict[str, Any] = {}

    if "supports_vision" in entry:
        caps["supports_vision"] = bool(entry["supports_vision"])
    if "supports_function_calling" in entry:
        caps["supports_function_calling"] = bool(entry["supports_function_calling"])

    caps["supports_streaming"] = True

    if entry.get("max_input_tokens"):
        caps["context_window"] = int(entry["max_input_tokens"])
    if entry.get("max_output_tokens"):
        caps["max_output_tokens"] = int(entry["max_output_tokens"])

    model_type = _normalize_mode(entry.get("mode"))
    if model_type:
        caps["model_type"] = model_type

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


def _find_entry(registry: dict[str, Any], model_code: str) -> dict[str, Any] | None:
    """
    使用多策略匹配查找模型条目 / Find a model entry using multi-strategy matching.

    Strategy order:
    1. Exact match: "gpt-4o"
    2. Provider-prefixed: try common prefixes like "openai/gpt-4o", "deepseek/deepseek-chat"
    3. Suffix match: find a key that ends with "/" + model_code
    """
    if model_code in registry:
        entry = registry[model_code]
        if isinstance(entry, dict):
            return entry

    common_prefixes = [
        "openai/", "azure/", "anthropic/", "deepseek/", "google/",
        "cohere/", "mistral/", "groq/", "together_ai/", "fireworks_ai/",
        "volcengine/", "huggingface/", "ollama/", "bedrock/",
    ]
    for prefix in common_prefixes:
        key = f"{prefix}{model_code}"
        if key in registry:
            entry = registry[key]
            if isinstance(entry, dict):
                return entry

    suffix = f"/{model_code}"
    for key, entry in registry.items():
        if key.endswith(suffix) and isinstance(entry, dict):
            return entry

    return None


async def lookup(model_code: str) -> dict[str, Any] | None:
    """
    查找模型代码对应的能力信息 / Look up capabilities for a model code.

    Returns dict with capability fields, or None if not found.
    """
    registry = await get_registry()
    if not registry:
        return None

    entry = _find_entry(registry, model_code)
    if not entry:
        return None

    return _extract_capabilities(entry)


async def enrich_remote_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        entry = _find_entry(registry, model_id)
        if entry:
            model = {**model, "capabilities": _extract_capabilities(entry)}
        enriched.append(model)

    return enriched


__all__ = ["enrich_remote_models", "lookup"]
