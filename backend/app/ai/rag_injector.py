"""
RAG 注入器

独立于 Engine 的 RAG 上下文注入模块。
从知识库检索相关分块并注入到 system_prompt 末尾。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.models.ai.agent import Agent

from app.ai.types import ChatMessage
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.rag_injector")


def merge_kb_ids(
    agent_kb_ids: list[int] | None,
    request_kb_ids: list[int] | None,
) -> list[int] | None:
    """合并 agent 绑定的知识库 IDs 和用户 @ 选择的知识库 IDs（去重保序）"""
    combined: list[int] = []
    seen: set[int] = set()
    for ids in (agent_kb_ids, request_kb_ids):
        if ids:
            for kid in ids:
                if kid not in seen:
                    seen.add(kid)
                    combined.append(kid)
    return combined or None


async def inject_rag_context(
    db: AsyncSession,
    agent: Agent,
    messages: list[ChatMessage],
    tenant_id: int,
    kb_ids: list[int] | None = None,
    rag_config: dict[str, Any] | None = None,
) -> tuple[list[ChatMessage], list[dict[str, Any]] | None]:
    """
    将 RAG 上下文注入 system_prompt

    如果提供了知识库 IDs，检索相关分块并注入到 system 消息末尾。
    未提供知识库时直接返回原始消息。

    Args:
        db: 数据库会话
        agent: 智能体模型实例
        messages: 已构建的消息列表（第一条为 system）
        tenant_id: 租户 ID
        kb_ids: 知识库 ID 列表（已合并 agent + 用户 @ 选择）
        rag_config: RAG 配置（来自 Skill 解析）

    Returns:
        (messages, rag_sources): 注入后的消息列表 + 引用来源列表（无 RAG 时为 None）
    """
    if not kb_ids:
        return messages, None

    rag_config = rag_config or {}

    try:
        from app.ai.rag.context_builder import RAGContextBuilder
        from app.ai.rag.retriever import HybridRetriever
        from app.ai.utils.token_estimator import estimate_tokens
        from app.repositories.ai.knowledge_base_repository import (
            AdminKnowledgeBaseRepository,
            KnowledgeBaseRepository,
        )

        # 获取知识库（用于 Embedding 模型配置）
        # 租户场景：使用 KnowledgeBaseRepository 确保租户隔离（visibility 控制跨租户访问）
        # 平台管理员场景：使用 AdminKnowledgeBaseRepository（无 tenant_id 限制）
        if tenant_id:
            kb_repo = KnowledgeBaseRepository(db, tenant_id=tenant_id)
        else:
            kb_repo = AdminKnowledgeBaseRepository(db)

        # 安全校验：验证所有 kb_ids 均属于当前租户（防止跨租户数据泄露）
        # 只有通过 tenant-scoped repo 校验的 KB 才允许检索
        validated_kb_ids: list[int] = []
        primary_kb = None
        for kid in kb_ids:
            kb = await kb_repo.get_by_id(kid)
            if kb:
                validated_kb_ids.append(kid)
                if primary_kb is None:
                    primary_kb = kb
            else:
                logger.warning(
                    "KB %d not accessible for tenant %d, skipped",
                    kid, tenant_id,
                )

        if not primary_kb or not validated_kb_ids:
            return messages, None

        kb_ids = validated_kb_ids

        # 提取用户最新问题
        user_query = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_query = msg.content
                break

        if not user_query:
            return messages, None

        # 检索
        retriever = HybridRetriever(db, tenant_id)
        chunks = await retriever.search(
            knowledge_base=primary_kb,
            query=user_query,
            top_k=rag_config.get("top_k", primary_kb.top_k),
            score_threshold=rag_config.get("score_threshold", primary_kb.score_threshold),
            search_mode=rag_config.get("search_mode"),
            kb_ids=kb_ids,
            rewrite_strategy=rag_config.get("rewrite_strategy", "none"),
            reranker_enabled=rag_config.get("reranker_enabled", False),
        )

        if not chunks:
            return messages, None

        # 计算 Token 预算
        builder = RAGContextBuilder(
            context_token_ratio=rag_config.get("context_token_ratio", 0.6),
        )

        # 估算 system prompt 的 token 数
        system_tokens = estimate_tokens(messages[0].content) if messages else 0
        # 从关联的 AIModel 获取实际上下文窗口大小
        model_context = 0
        if hasattr(agent, "model") and agent.model:
            model_context = getattr(agent.model, "context_window", 0) or 0
        max_context = model_context or 8000

        rag_budget, _ = builder.calculate_rag_budget(
            max_context_tokens=max_context,
            system_prompt_tokens=system_tokens,
            max_tokens=agent.max_tokens,
        )

        # 构建 RAG 上下文
        rag_context = builder.build_rag_context(chunks, rag_budget)

        if not rag_context.rag_text:
            return messages, None

        # 注入到 system 消息末尾
        if messages and messages[0].role == "system":
            messages[0] = ChatMessage(
                role="system",
                content=messages[0].content + "\n" + rag_context.rag_text,
            )

        # 构建引用来源
        sources = [s.to_dict() for s in rag_context.sources]

        logger.info(
            "RAG injected: agent=%d, chunks=%d, tokens=%d",
            agent.id, rag_context.chunk_count, rag_context.token_count,
        )

        return messages, sources

    except Exception as exc:
        logger.warning(
            "RAG injection failed for agent %d: %s",
            agent.id, str(exc),
        )
        return messages, None


__all__ = ["inject_rag_context", "merge_kb_ids"]
