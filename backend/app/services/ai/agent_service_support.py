"""
Agent service shared helpers / 智能体服务共享辅助函数。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import AudienceEnum, UserRoleEnum
from app.enums.knowledge_base import RewriteStrategyEnum, SearchModeEnum
from app.exceptions import BusinessException
from app.repositories.ai import AIModelRepository

logger = LogManager.get_logger("ai.agent_service")

# 版本快照字段：从 Agent 复制到 AgentVersion 的字段列表
VERSION_SNAPSHOT_FIELDS = [
    "system_prompt",
    "model_id",
    "temperature",
    "max_tokens",
    "top_p",
    "execution_mode",
    "input_variables",
    "welcome_message",
    "suggested_questions",
    "quota_config",
    "rag_config",
    "context_config",
    "output_schema",
    # NOTE: knowledge_base_ids removed —
    # replaced by direct AgentSkillGrant + AgentKnowledgeBaseBinding architecture / 已由 AgentSkillGrant 等替代 / replaced by grants
]


def normalize_agent_rag_config(raw: Any) -> dict[str, Any] | None:
    """Validate mutable Agent.rag_config fields / 校验并归一化可写的 Agent.rag_config 字段。"""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BusinessException(message=_("agent.error.invalid_rag_config"))

    normalized = dict(raw)

    def _raise_invalid(field: str) -> None:
        raise BusinessException(
            message=_("agent.error.invalid_rag_config_field").format(field=field)
        )

    search_mode = raw.get("search_mode")
    if search_mode is not None:
        allowed_search_modes = {item.value for item in SearchModeEnum}
        if search_mode not in allowed_search_modes:
            _raise_invalid("search_mode")

    rewrite_strategy = raw.get("rewrite_strategy")
    if rewrite_strategy is not None:
        allowed_rewrite_strategies = {item.value for item in RewriteStrategyEnum}
        if rewrite_strategy not in allowed_rewrite_strategies:
            _raise_invalid("rewrite_strategy")

    if "top_k" in raw and raw.get("top_k") is not None:
        top_k = raw.get("top_k")
        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not (1 <= top_k <= 20)
        ):
            _raise_invalid("top_k")
        normalized["top_k"] = top_k

    if "score_threshold" in raw and raw.get("score_threshold") is not None:
        score_threshold = raw.get("score_threshold")
        if isinstance(score_threshold, bool) or not isinstance(
            score_threshold, (float, int)
        ):
            _raise_invalid("score_threshold")
        score_threshold = float(score_threshold)
        if not (0.0 <= score_threshold <= 1.0):
            _raise_invalid("score_threshold")
        normalized["score_threshold"] = score_threshold

    if "reranker_enabled" in raw and raw.get("reranker_enabled") is not None:
        reranker_enabled = raw.get("reranker_enabled")
        if not isinstance(reranker_enabled, bool):
            _raise_invalid("reranker_enabled")
        normalized["reranker_enabled"] = reranker_enabled

    if "context_token_ratio" in raw and raw.get("context_token_ratio") is not None:
        context_token_ratio = raw.get("context_token_ratio")
        if isinstance(context_token_ratio, bool) or not isinstance(
            context_token_ratio, (float, int)
        ):
            _raise_invalid("context_token_ratio")
        context_token_ratio = float(context_token_ratio)
        if not (0.1 <= context_token_ratio <= 0.9):
            _raise_invalid("context_token_ratio")
        normalized["context_token_ratio"] = context_token_ratio

    return normalized


def role_ids_allow(role_ids: list[int] | None, user_role_id: int | None) -> bool:
    """Resolve internal role restriction semantics / 解析端内角色限制语义."""
    if role_ids is None:
        return True
    if not role_ids:
        return False
    if user_role_id is None:
        return False
    return user_role_id in role_ids


def audience_allows_role(target_audience: str | None, user_role: str | None) -> bool:
    """Resolve target_audience visibility semantics before access-rule lookup."""
    if user_role is None:
        return True
    if target_audience == AudienceEnum.ALL.value:
        return True
    if target_audience == AudienceEnum.ADMIN_TENANT.value:
        return user_role in (
            UserRoleEnum.PLATFORM_ADMIN.value,
            UserRoleEnum.TENANT_ADMIN.value,
        )
    if target_audience == AudienceEnum.ADMIN_ONLY.value:
        return user_role == UserRoleEnum.PLATFORM_ADMIN.value
    return True


async def validate_agent_max_tokens_against_model(
    db: Any,
    *,
    model_id: int | None,
    max_tokens: int | None,
) -> None:
    """Ensure agent max_tokens does not exceed model max_output_tokens / 校验智能体 max_tokens 不超过模型 max_output_tokens."""
    if model_id is None or max_tokens is None:
        return

    model_repo = AIModelRepository(db)
    model = await model_repo.get_by_id(model_id)
    if not model:
        return

    model_limit = getattr(model, "max_output_tokens", None)
    if model_limit is None or max_tokens <= model_limit:
        return

    raise BusinessException(
        message=_("agent.error.max_tokens_exceeds_model_limit").format(
            max_tokens=max_tokens,
            model_limit=model_limit,
            model_name=getattr(model, "name", model_id),
        ),
    )


async def clear_cascaded_conversation_memories(
    targets: list[tuple[int, int]],
) -> int:
    """Best-effort clear session memories for cascaded conversation deletes / 级联删除会话后的记忆最佳努力清理。"""
    if not targets:
        return 0

    from app.services.ai.session_memory_service import SessionMemoryService

    grouped: dict[int, list[int]] = defaultdict(list)
    for tenant_id, conversation_id in targets:
        grouped[int(tenant_id)].append(int(conversation_id))

    total_deleted = 0
    for tenant_id, conversation_ids in grouped.items():
        try:
            total_deleted += await SessionMemoryService(
                tenant_id
            ).clear_conversation_memories(
                conversation_ids,
            )
        except Exception as exc:
            logger.warning(
                "Cascade conversation memory cleanup failed: tenant={} count={} err={}",
                tenant_id,
                len(conversation_ids),
                str(exc),
            )
    return total_deleted
