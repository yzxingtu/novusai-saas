"""
Built-in scheduled tasks / 内置定时任务

System built-in periodic maintenance tasks.
系统内置的周期性维护任务
Note: Celery Worker is an independent synchronous process that does not go through FastAPI lifespan,
so RedisManager will not be initialized. All Redis operations must use a sync redis client.
注意：Celery Worker 是独立的同步进程，不经过 FastAPI lifespan，
因此 RedisManager 不会被初始化。所有 Redis 操作必须使用同步 redis 客户端。
"""

import contextlib
from datetime import timedelta
from typing import Any

import redis

from app.core.base_model import utc_now
from app.core.config import settings
from app.core.database import sync_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")


def _get_sync_redis() -> redis.Redis:
    """Get sync Redis client (Celery Worker only) / 获取同步 Redis 客户端（Celery Worker 专用）"""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@register_task(
    queue="scheduled",
    description="Clean up expired captcha cache / 清理过期验证码缓存",
    max_retries=1,
)
def clean_expired_captchas(self: BaseTask) -> dict:
    try:
        client = _get_sync_redis()
        cursor: int | str = 0
        cleaned = 0
        while True:
            cursor, keys = client.scan(
                cursor=cursor,
                match="captcha:*",
                count=100,
            )
            if keys:
                ttls = [client.ttl(key) for key in keys]
                expired_keys = [
                    k for k, t in zip(keys, ttls, strict=False) if t == -1
                ]
                if expired_keys:
                    cleaned += client.delete(*expired_keys)
            if cursor == 0:
                break
        logger.info("{} count={}", _("task.log.captcha_cleaned"), cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning("{} error={}", _("task.log.captcha_cleanup_skipped"), str(e))
        return {"cleaned": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="System health check (Redis/DB connection status) / 系统健康检查（Redis/DB 连接状态）",
    max_retries=1,
)
def system_health_check(self: BaseTask) -> dict:
    results: dict = {
        "timestamp": utc_now().isoformat(),
        "db": "unknown",
        "redis": "unknown",
    }

    session = None
    try:
        session = sync_session_factory()
        from sqlalchemy import text
        session.execute(text("SELECT 1"))
        results["db"] = "connected"
    except Exception as e:
        results["db"] = f"error: {e}"
    finally:
        if session:
            session.close()

    try:
        client = _get_sync_redis()
        results["redis"] = "connected" if client.ping() else "disconnected"
    except Exception as e:
        results["redis"] = f"error: {e}"

    logger.info(f"Health check: db={results['db']}, redis={results['redis']}")
    return results


@register_task(
    queue="scheduled",
    description="Reset agent daily quotas (clean up Redis keys without TTL) / 重置智能体每日配额（清理无 TTL 的 Redis key）",
    max_retries=1,
)
def reset_agent_daily_quotas(self: BaseTask) -> dict:
    try:
        client = _get_sync_redis()
        cleaned = 0
        patterns = [
            "ai:agent_quota:daily:*",
            "ai:agent_quota:daily_conv:*",
            "ai:agent_quota:user:*",
        ]
        for pattern in patterns:
            cursor: int | str = 0
            while True:
                cursor, keys = client.scan(
                    cursor=cursor, match=pattern, count=200,
                )
                if keys:
                    ttls = [client.ttl(key) for key in keys]
                    no_ttl = [
                        k for k, t in zip(keys, ttls, strict=False) if t == -1
                    ]
                    if no_ttl:
                        cleaned += client.delete(*no_ttl)
                if cursor == 0:
                    break
        logger.info("{} count={}", _("task.log.quota_reset"), cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning("{} error={}", _("task.log.quota_reset_skipped"), str(e))
        return {"cleaned": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="Reset agent daily stats (Redis daily count reset) / 重置智能体每日统计（Redis 当日计数归零）",
    max_retries=1,
)
def reset_agent_daily_stats(self: BaseTask) -> dict:
    try:
        client = _get_sync_redis()
        cursor: int | str = 0
        reset_count = 0
        while True:
            cursor, keys = client.scan(
                cursor=cursor, match="ai:agent_stats:daily:*", count=200,
            )
            if keys:
                reset_count += client.delete(*keys)
            if cursor == 0:
                break
        logger.info("{} count={}", _("task.log.stats_reset"), reset_count)
        return {"reset_count": reset_count}
    except Exception as e:
        logger.warning("{} error={}", _("task.log.stats_reset_skipped"), str(e))
        return {"reset_count": 0, "error": str(e)}


@register_task(
    queue="scheduled",
    description="Check plugin license expirations, auto-disable expired plugins and send warnings / 检查插件 License 到期，自动禁用到期插件并发出预警提醒",
    max_retries=1,
)
def check_plugin_trial_expirations(self: BaseTask) -> dict:
    """Check plugin trial/fixed-term license expiry; auto-disable on expiry. / 检查插件 trial/fixed-term License 到期情况，到期自动禁用。"""
    import asyncio

    from app.tasks.async_db import task_async_session

    async def _run():
        from app.core.redis import RedisManager
        from app.plugins.license import check_plugin_license_expirations

        # Celery worker doesn't go through FastAPI lifespan, RedisManager is not initialized.
        # Celery worker 不走 FastAPI lifespan，RedisManager 未初始化。
        # lifecycle.disable() → _plugin_lock() → get_redis_client() needs Redis.
        # lifecycle.disable() → _plugin_lock() → get_redis_client() 需要 Redis。
        # Without initialization, disable() will silently fail (RuntimeError caught by license.py),
        # and plugins will never be disabled even if trial period has expired.
        # 若不初始化，disable() 会 silently fail (RuntimeError 被 license.py 捕获)，
        # 插件将永远不会被禁用，即使试用期已到期。
        redis_was_initialized = RedisManager._pool is not None
        if not redis_was_initialized:
            try:
                await RedisManager.init()
            except Exception as redis_err:
                # Redis unavailable: downgrade — license will still be marked invalid, but disable() may fail
                # Redis 不可用时降级：license 仍会标记为 invalid，但 disable() 可能失败
                logger.warning(
                    "Plugin trial check: Redis unavailable ({}), "
                    "plugin disable may fail (license will still be invalidated)",
                    redis_err,
                )

        try:
            async with task_async_session() as db:
                actions = await check_plugin_license_expirations(db)
                await db.commit()
                return actions
        finally:
            # If this call initialized Redis, close connection pool to avoid reusing old pool across event-loop
            # 若本次调用初始化了 Redis，关闭连接池避免跨 event-loop 复用旧 pool
            if not redis_was_initialized:
                with contextlib.suppress(Exception):
                    await RedisManager.close()

    try:
        loop = asyncio.new_event_loop()
        try:
            actions = loop.run_until_complete(_run())
        finally:
            loop.close()

        disabled = [a for a in actions if a.get("action") == "disabled"]
        warnings = [a for a in actions if a.get("action") == "warning"]
        if disabled or warnings:
            logger.info(
                "Plugin license check: disabled={}, warnings={}",
                len(disabled), len(warnings),
            )
        return {"disabled": len(disabled), "warnings": len(warnings), "total": len(actions)}
    except Exception as exc:
        logger.warning("Plugin license check failed: {}", exc)
        return {"disabled": 0, "warnings": 0, "error": str(exc)}


@register_task(
    queue="scheduled",
    description="Clean up expired task logs (retain 30 days) / 清理过期任务日志（保留 30 天）",
    max_retries=1,
)
def clean_expired_task_logs(self: BaseTask) -> dict:
    session = None
    try:
        from app.models.system.task_log import TaskLog

        session = sync_session_factory()
        cutoff = utc_now() - timedelta(days=30)
        result = (
            session.query(TaskLog)
            .filter(TaskLog.created_at < cutoff)
            .update({"is_deleted": True})
        )
        session.commit()
        logger.info("{} count={}", _("task.log.task_log_cleaned"), result)
        return {"deleted": result}
    except Exception as e:
        if session:
            session.rollback()
        logger.error("{} error={}", _("task.log.task_log_cleanup_failed"), str(e))
        return {"deleted": 0, "error": str(e)}
    finally:
        if session:
            session.close()


@register_task(
    queue="scheduled",
    description="Clean up expired session memories (24h fallback) / 清理过期会话记忆（24h 兜底）",
    max_retries=1,
)
def clean_expired_session_memories(self: BaseTask) -> dict:
    """
    Clean up expired session memory keys (fallback) / 清理过期会话记忆 key（兜底）

    Note:
    - Normally session memory keys auto-expire via TTL;
    - 正常情况下会话记忆 key 使用 TTL 自动过期；
    - This task provides fallback cleanup for keys without TTL or abnormal residual keys.
    - 本任务用于兜底清理无 TTL 或异常残留 key。
    """
    try:
        client = _get_sync_redis()
        cursor: int | str = 0
        cleaned = 0
        while True:
            cursor, keys = client.scan(
                cursor=cursor,
                match="mem:sess:*",
                count=200,
            )
            if keys:
                ttls = [client.ttl(key) for key in keys]
                # ttl == -1 means no expiration, needs cleanup / ttl == -1 表示无过期时间，需要清理
                no_ttl = [
                    k for k, t in zip(keys, ttls, strict=False) if t == -1
                ]
                if no_ttl:
                    cleaned += client.delete(*no_ttl)
            if cursor == 0:
                break
        logger.info("Session memory cleanup finished, cleaned={}", cleaned)
        return {"cleaned": cleaned}
    except Exception as e:
        logger.warning("Session memory cleanup skipped: {}", str(e))
        return {"cleaned": 0, "error": str(e)}


# ── LiteLLM Model Capability Registry Sync / LiteLLM 模型能力注册表同步 ─────────

LLMRING_REGISTRY_BASE = "https://llmring.github.io/registry"
LLMRING_PROVIDERS = ["openai", "anthropic", "google"]
REQUEST_TIMEOUT = 30
DASHSCOPE_MODEL_DOC_URL = "https://www.alibabacloud.com/help/en/model-studio/models"
DASHSCOPE_RATE_LIMIT_DOC_URL = "https://www.alibabacloud.com/help/en/model-studio/rate-limit"
DASHSCOPE_SUPPLEMENT_DEFAULTS: dict[str, dict] = {
    "qwen-max": {"mode": "chat"},
    "qwen-max-latest": {"mode": "chat"},
    "qwen-vl-max": {"mode": "chat", "supports_vision": True},
    "qwen-vl-max-latest": {"mode": "chat", "supports_vision": True},
    "qwen-vl-plus": {"mode": "chat", "supports_vision": True},
    "qwen-vl-plus-latest": {"mode": "chat", "supports_vision": True},
}

LITELLM_REGISTRY_URLS = [
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/model_prices_and_context_window.json",
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
]
LITELLM_REDIS_KEY = "ai:litellm:registry"
LITELLM_REDIS_TTL = 86400 * 3


def _is_valid_litellm_entry(key: str, entry: dict) -> bool:
    """
    Filter out sample_spec and invalid entries. / 过滤 sample_spec 及无效条目。
    """
    if key == "sample_spec":
        return False
    return isinstance(entry, dict) and len(entry) > 0


def _parse_bool_safe(raw_value: object) -> bool | None:
    """
    Parse boolean explicitly; avoid bool(raw_value) which treats "false" as True.
    显式解析布尔值；避免 bool(raw_value) 将 "false" 转为 True。
    """
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        s = raw_value.strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no"):
            return False
    return None


def _normalize_llmring_entry(raw: dict) -> dict:
    """
    Normalize LLMRing entry to LiteLLM-style for downstream _extract_capabilities.
    将 LLMRing 条目归一化为 LiteLLM 风格，供下游 _extract_capabilities 消费。
    """
    out: dict = {}
    if raw.get("max_input_tokens") is not None:
        try:
            out["max_input_tokens"] = int(raw["max_input_tokens"])
        except (TypeError, ValueError):
            pass
    if raw.get("max_output_tokens") is not None:
        try:
            out["max_output_tokens"] = int(raw["max_output_tokens"])
        except (TypeError, ValueError):
            pass
    if raw.get("dollars_per_million_tokens_input") is not None:
        try:
            val = float(raw["dollars_per_million_tokens_input"])
            out["input_cost_per_token"] = val / 1_000_000
        except (TypeError, ValueError):
            pass
    if raw.get("dollars_per_million_tokens_output") is not None:
        try:
            val = float(raw["dollars_per_million_tokens_output"])
            out["output_cost_per_token"] = val / 1_000_000
        except (TypeError, ValueError):
            pass
    mode = raw.get("mode")
    out["mode"] = str(mode) if mode else "chat"
    for field in ("supports_vision", "supports_function_calling", "supports_streaming"):
        if field in raw:
            parsed = _parse_bool_safe(raw[field])
            if parsed is not None:
                out[field] = parsed
    return out


def _merge_entry_fill_empty(target: dict, source: dict) -> None:
    """
    Fill only empty slots in target; do not overwrite existing non-empty values.
    只填空位，不覆盖主源已有值。
    """
    for k, v in source.items():
        if v is None or (isinstance(v, str) and v.strip() == ""):
            continue
        if k not in target or target[k] is None or (
            isinstance(target[k], str) and target[k].strip() == ""
        ):
            target[k] = v


def _find_registry_key_for_model_id(
    registry: dict, model_id: str, reg_key: str
) -> str | None:
    """
    Find an existing registry key for the given model_id (for dedup).
    reg_key exists: return reg_key; else search by model_id suffix.
    按 model_id 查找可复用的 registry key，用于去重。
    """
    if reg_key in registry:
        return reg_key
    suffix = f"/{model_id}"
    for key in registry:
        if key == model_id or key.endswith(suffix):
            return key
    return None


def _build_registry_from_litellm(raw: dict) -> tuple[dict, int]:
    """
    Build main registry from LiteLLM payload; return (registry, valid_key_count).
    从 LiteLLM 数据构建主 registry，返回有效 key 数。
    """
    registry: dict = {}
    count = 0
    for key, entry in raw.items():
        if _is_valid_litellm_entry(key, entry):
            registry[key] = dict(entry)
            count += 1
    return registry, count


def _merge_llmring_into_registry(registry: dict, payload: dict) -> int:
    """
    Merge LLMRing provider data into registry; return number of added keys.
    Key normalization: openai:gpt-4.1 -> openai/gpt-4.1 (replace first colon only).
    合并 LLMRing 补充源，返回新增 key 数。
    """
    models = payload.get("models") if isinstance(payload.get("models"), dict) else None
    if not models:
        return 0
    added = 0
    for raw_key, raw_entry in models.items():
        if not isinstance(raw_entry, dict):
            continue
        reg_key = str(raw_key).replace(":", "/", 1)  # openai:gpt-4.1 -> openai/gpt-4.1 / 注册键规范化
        model_id = raw_key.split(":", 1)[-1] if ":" in raw_key else raw_key
        normalized = _normalize_llmring_entry(raw_entry)
        if not normalized or (len(normalized) == 1 and normalized.get("mode") == "chat"):
            logger.debug("Skip empty LLMRing entry: reg_key={}", reg_key)
            continue
        existing_key = _find_registry_key_for_model_id(registry, model_id, reg_key)
        if existing_key:
            _merge_entry_fill_empty(registry[existing_key], normalized)
        else:
            registry[reg_key] = normalized
            added += 1
    return added


def _parse_int_from_text(raw_value: object) -> int | None:
    """Parse int from text like 1,000,000 / 从文本中解析整数。"""
    if raw_value is None:
        return None
    text = str(raw_value).replace(",", "").strip()
    if not text:
        return None
    digits = []
    for char in text:
        if char.isdigit():
            digits.append(char)
        elif digits:
            break
    if not digits:
        return None
    try:
        return int("".join(digits))
    except ValueError:
        return None


def _parse_price_per_token(raw_value: object) -> float | None:
    """Parse price cell like $0.21 (per 1M tokens) to per-token / 价格转 LiteLLM 每 token 单价。"""
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text.startswith("$"):
        return None
    try:
        return float(text[1:].replace(",", "")) / 1_000_000
    except ValueError:
        return None


def _extract_model_name_from_cell(cell_text: str) -> str:
    """Extract leading model code from table cell / 从表格首列提取模型编码。"""
    return str(cell_text).strip().split(" ", 1)[0]


def _find_table_row_by_model(soup: Any, model_id: str):
    """Find table row whose first cell starts with model_id / 按首列查找模型行。"""
    for row in soup.find_all("tr"):
        cells = [
            cell.get_text(" ", strip=True)
            for cell in row.find_all(["td", "th"], recursive=False)
        ]
        if cells and _extract_model_name_from_cell(cells[0]) == model_id:
            return row, cells
    return None, None


def _resolve_rate_limits_from_row(row, cells: list[str]) -> tuple[int | None, int | None]:
    """Resolve RPM/TPM from rate-limit table row / 从限流表解析 RPM 与 TPM。"""
    rpm = _parse_int_from_text(cells[1]) if len(cells) >= 3 else None
    tpm = _parse_int_from_text(cells[2]) if len(cells) >= 3 else None
    if rpm is not None and tpm is not None:
        return rpm, tpm

    cursor = row
    for _ in range(6):
        cursor = cursor.find_next_sibling("tr") if cursor else None
        if cursor is None:
            break
        next_cells = [
            cell.get_text(" ", strip=True)
            for cell in cursor.find_all(["td", "th"], recursive=False)
        ]
        if len(next_cells) < 3:
            continue
        rpm = _parse_int_from_text(next_cells[-2])
        tpm = _parse_int_from_text(next_cells[-1])
        if rpm is not None and tpm is not None:
            return rpm, tpm
    return None, None


def _build_dashscope_doc_entry(
    cells: list[str],
    *,
    fallback_entry: dict | None = None,
    defaults: dict | None = None,
    rpm_limit: int | None = None,
    tpm_limit: int | None = None,
) -> dict:
    """Build LiteLLM-style entry from DashScope docs row / 从 DashScope 文档行构建 LiteLLM 风格条目。"""
    entry = dict(fallback_entry or {})
    _merge_entry_fill_empty(entry, defaults or {})

    if len(cells) >= 7:
        context_window = _parse_int_from_text(cells[2])
        max_input_tokens = _parse_int_from_text(cells[3])
        max_output_tokens = _parse_int_from_text(cells[4])
        input_cost_per_token = _parse_price_per_token(cells[5])
        output_cost_per_token = _parse_price_per_token(cells[6])
        if context_window is not None:
            entry["context_window"] = context_window
        if max_input_tokens is not None:
            entry["max_input_tokens"] = max_input_tokens
        if max_output_tokens is not None:
            entry["max_output_tokens"] = max_output_tokens
        if input_cost_per_token is not None:
            entry["input_cost_per_token"] = input_cost_per_token
        if output_cost_per_token is not None:
            entry["output_cost_per_token"] = output_cost_per_token
    elif len(cells) >= 4:
        input_cost_per_token = _parse_price_per_token(cells[2])
        output_cost_per_token = _parse_price_per_token(cells[3])
        if input_cost_per_token is not None:
            entry["input_cost_per_token"] = input_cost_per_token
        if output_cost_per_token is not None:
            entry["output_cost_per_token"] = output_cost_per_token

    if rpm_limit is not None:
        entry["rpm"] = rpm_limit
    if tpm_limit is not None:
        entry["tpm"] = tpm_limit

    entry["litellm_provider"] = "dashscope"
    entry["source"] = DASHSCOPE_MODEL_DOC_URL
    return entry


def _fetch_dashscope_doc_supplements(registry: dict) -> dict[str, dict]:
    """Fetch targeted DashScope model metadata from official docs / 从官方文档抓取 DashScope 关键模型元数据。"""
    import requests
    from bs4 import BeautifulSoup

    model_resp = requests.get(DASHSCOPE_MODEL_DOC_URL, timeout=REQUEST_TIMEOUT)
    model_resp.raise_for_status()
    rate_resp = requests.get(DASHSCOPE_RATE_LIMIT_DOC_URL, timeout=REQUEST_TIMEOUT)
    rate_resp.raise_for_status()

    model_soup = BeautifulSoup(model_resp.text, "lxml")
    rate_soup = BeautifulSoup(rate_resp.text, "lxml")
    entries: dict[str, dict] = {}

    for model_id in DASHSCOPE_SUPPLEMENT_DEFAULTS:
        model_row, model_cells = _find_table_row_by_model(model_soup, model_id)
        rate_row, rate_cells = _find_table_row_by_model(rate_soup, model_id)
        if not model_cells:
            continue

        rpm_limit, tpm_limit = (None, None)
        if rate_row and rate_cells:
            rpm_limit, tpm_limit = _resolve_rate_limits_from_row(rate_row, rate_cells)

        fallback_entry = registry.get(f"dashscope/{model_id}")
        if fallback_entry is None and model_id.endswith("-latest"):
            base_model_id = model_id[: -len("-latest")]
            fallback_entry = entries.get(f"dashscope/{base_model_id}")
            if fallback_entry is None:
                fallback_entry = registry.get(f"dashscope/{base_model_id}")

        entries[f"dashscope/{model_id}"] = _build_dashscope_doc_entry(
            model_cells,
            fallback_entry=fallback_entry,
            defaults=DASHSCOPE_SUPPLEMENT_DEFAULTS.get(model_id),
            rpm_limit=rpm_limit,
            tpm_limit=tpm_limit,
        )

    return entries


def _merge_dashscope_supplements_into_registry(registry: dict) -> int:
    """Merge DashScope official-doc supplements into registry / 合并 DashScope 官方文档补充源。"""
    additions = 0
    for key, entry in _fetch_dashscope_doc_supplements(registry).items():
        if key in registry:
            _merge_entry_fill_empty(registry[key], entry)
            continue
        registry[key] = entry
        additions += 1
    return additions


@register_task(
    queue="scheduled",
    description="Sync LiteLLM + LLMRing multi-source model registry to Redis / 同步 LiteLLM + LLMRing 多源模型能力注册表到 Redis",
    max_retries=2,
)
def sync_litellm_registry(self: BaseTask) -> dict:
    """
    Multi-source sync: LiteLLM (primary) + LLMRing (supplement), merge and write to Redis.
    多源同步：LiteLLM 主源 + LLMRing 补充，合并后写入 Redis。
    """
    import json

    import requests

    last_error: Exception | None = None
    registry: dict | None = None
    litellm_keys = 0
    llmring_added_keys = 0
    dashscope_added_keys = 0
    source_url: str | None = None

    for url in LITELLM_REGISTRY_URLS:
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()

            raw = resp.json()
            if not isinstance(raw, dict) or len(raw) < 10:
                logger.warning(
                    "LiteLLM registry looks invalid, entries={}",
                    len(raw) if isinstance(raw, dict) else "N/A",
                )
                continue

            registry, litellm_keys = _build_registry_from_litellm(raw)
            llmring_added_keys = 0
            source_url = url

            for provider in LLMRING_PROVIDERS:
                llmring_url = f"{LLMRING_REGISTRY_BASE}/{provider}/models.json"
                try:
                    llm_resp = requests.get(llmring_url, timeout=REQUEST_TIMEOUT)
                    llm_resp.raise_for_status()
                    payload = llm_resp.json()
                    if not isinstance(payload, dict):
                        raise ValueError("LLMRing response is not a dict")
                    added = _merge_llmring_into_registry(registry, payload)
                    llmring_added_keys += added
                except Exception as llm_err:
                    logger.warning(
                        "LLMRing provider fetch failed: provider={} error={}",
                        provider,
                        str(llm_err),
                    )
            try:
                dashscope_added_keys = _merge_dashscope_supplements_into_registry(
                    registry
                )
            except Exception as dashscope_err:
                logger.warning(
                    "DashScope supplement fetch failed: error={}",
                    str(dashscope_err),
                )
            break
        except Exception as e:
            last_error = e
            logger.warning(
                "LiteLLM registry fetch failed: url={} error={}", url, str(e)
            )

    if registry is None or source_url is None:
        raise RuntimeError(f"All LiteLLM registry URLs failed: {last_error}")

    client = _get_sync_redis()
    client.setex(
        LITELLM_REDIS_KEY,
        LITELLM_REDIS_TTL,
        json.dumps(registry, ensure_ascii=False),
    )
    model_count = len(registry)
    logger.info(
        "LiteLLM registry synced: source={} models={} litellm_keys={} llmring_added={} dashscope_added={}",
        source_url,
        model_count,
        litellm_keys,
        llmring_added_keys,
        dashscope_added_keys,
    )
    return {
        "source": source_url,
        "model_count": model_count,
        "litellm_keys": litellm_keys,
        "llmring_added_keys": llmring_added_keys,
        "dashscope_added_keys": dashscope_added_keys,
    }
