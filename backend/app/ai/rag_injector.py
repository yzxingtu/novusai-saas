"""
RAG Injector / RAG 注入器

Engine-independent RAG context injection module.
Retrieves relevant chunks from knowledge bases and injects them into system_prompt.
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
    """Merge agent-bound KB IDs and user @-selected KB IDs (deduplicated, order-preserved) / 合并 agent 绑定的知识库 IDs 和用户 @ 选择的知识库 IDs（去重保序）"""
    combined: list[int] = []
    seen: set[int] = set()
    for ids in (agent_kb_ids, request_kb_ids):
        if ids:
            for kid in ids:
                if kid not in seen:
                    seen.add(kid)
                    combined.append(kid)
    return combined or None


async def load_agent_kb_bindings(
    db: AsyncSession,
    agent_id: int,
    tenant_id: int,
) -> tuple[list[int] | None, dict[int, float]]:
    """
    Load enabled bindings from AgentKnowledgeBaseBinding junction table.
    从 AgentKnowledgeBaseBinding 中间表加载 enabled=True 的绑定。

    Includes platform-global rows (tenant_id IS NULL) plus this tenant's overlay rows.
    含平台全局绑定（tenant_id 为空）与本企业的叠加绑定，避免跨企业泄露扩展知识库。

    Returns:
        (kb_ids, kb_weights): KB ID list + {kb_id: weight} mapping / 知识库 ID 列表 + {kb_id: weight} 映射
    """
    from sqlalchemy import or_, select

    from app.models.ai.agent_kb_binding import AgentKnowledgeBaseBinding

    stmt = (
        select(AgentKnowledgeBaseBinding)
        .where(
            AgentKnowledgeBaseBinding.agent_id == agent_id,
            AgentKnowledgeBaseBinding.enabled.is_(True),
            AgentKnowledgeBaseBinding.is_deleted.is_(False),
            or_(
                AgentKnowledgeBaseBinding.tenant_id.is_(None),
                AgentKnowledgeBaseBinding.tenant_id == tenant_id,
            ),
        )
        .order_by(AgentKnowledgeBaseBinding.sort_order)
    )
    result = await db.execute(stmt)
    bindings = result.scalars().all()

    if not bindings:
        return None, {}

    from app.services.ai.tenant_platform_kb_suppression_service import (
        load_suppressed_platform_kb_ids,
    )

    suppressed = await load_suppressed_platform_kb_ids(db, tenant_id, agent_id)

    kb_ids: list[int] = []
    kb_weights: dict[int, float] = {}
    for b in bindings:
        kid = b.knowledge_base_id
        if b.tenant_id is None and kid in suppressed:
            continue
        kb_ids.append(kid)
        kb_weights[kid] = b.weight

    if not kb_ids:
        return None, {}
    return kb_ids, kb_weights


async def inject_rag_context(
    db: AsyncSession,
    agent: Agent,
    messages: list[ChatMessage],
    tenant_id: int,
    kb_ids: list[int] | None = None,
    rag_config: dict[str, Any] | None = None,
    kb_weights: dict[int, float] | None = None,
) -> tuple[list[ChatMessage], list[dict[str, Any]] | None]:
    """
    Inject RAG context into system_prompt.
    将 RAG 上下文注入 system_prompt。

    If KB IDs are provided, retrieves relevant chunks and appends to system message.
    Returns original messages when no KB IDs are provided.
    如果提供了知识库 IDs，检索相关分块并注入到 system 消息末尾。
    未提供知识库时直接返回原始消息。

    Args:
        db: Database session / 数据库会话
        agent: Agent model instance / 智能体模型实例
        messages: Built message list (first is system) / 已构建的消息列表（第一条为 system）
        tenant_id: Tenant ID / 企业 ID
        kb_ids: KB ID list (merged Agent binding + user @ selection) / 知识库 ID 列表（已合并 Agent 绑定 + 用户 @ 选择）
        rag_config: RAG config (from agent.rag_config) / RAG 配置（来自 agent.rag_config）
        kb_weights: {kb_id: weight} mapping from AgentKnowledgeBaseBinding / {kb_id: weight} 映射，来自 AgentKnowledgeBaseBinding

    Returns:
        (messages, rag_sources): Injected message list + citation sources (None if no RAG)
        注入后的消息列表 + 引用来源列表（无 RAG 时为 None）
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

        # Get knowledge bases (for Embedding model config) / 获取知识库（用于 Embedding 模型配置）
        # Tenant scenario: KnowledgeBaseRepository ensures tenant isolation (visibility controls cross-tenant access)
        # 企业场景：使用 KnowledgeBaseRepository 确保企业隔离（visibility 控制跨企业访问）
        # Admin scenario: AdminKnowledgeBaseRepository (no tenant_id restriction)
        # 平台管理员场景：使用 AdminKnowledgeBaseRepository（无 tenant_id 限制）
        if tenant_id:
            kb_repo = KnowledgeBaseRepository(db, tenant_id=tenant_id)
        else:
            kb_repo = AdminKnowledgeBaseRepository(db)

        # Security check: verify all kb_ids belong to current tenant (prevent cross-tenant data leak)
        # 安全校验：验证所有 kb_ids 均属于当前企业（防止跨企业数据泄露）
        # Only KBs passing tenant-scoped repo validation are allowed for retrieval
        # 只有通过 tenant-scoped repo 校验的 KB 才允许检索
        validated_kb_ids: list[int] = []
        validated_kbs = []
        for kid in kb_ids:
            kb = await kb_repo.get_by_id(kid)
            if kb:
                validated_kb_ids.append(kid)
                validated_kbs.append(kb)
            else:
                logger.warning(
                    "KB {} not accessible for tenant {}, skipped",
                    kid, tenant_id,
                )

        if not validated_kbs or not validated_kb_ids:
            return messages, None

        kb_ids = validated_kb_ids

        # Extract user's latest question / 提取用户最新问题
        user_query = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_query = msg.content
                break

        if not user_query:
            return messages, None

        # Retrieval / 检索
        retriever = HybridRetriever(db, tenant_id)
        # RAG retrieval params unified from Agent.rag_config, no longer falling back to KB model fields
        # RAG 检索参数统一从 Agent.rag_config 读取，不再回退到 KB 模型字段
        chunks = await retriever.search(
            query=user_query,
            top_k=rag_config.get("top_k", 5),
            score_threshold=rag_config.get("score_threshold", 0.5),
            search_mode=rag_config.get("search_mode", "hybrid"),
            kb_ids=kb_ids,
            rewrite_strategy=rag_config.get("rewrite_strategy", "none"),
            reranker_enabled=rag_config.get("reranker_enabled", False),
            knowledge_bases=validated_kbs,
            kb_weights=kb_weights,
        )

        if not chunks:
            return messages, None

        kb_name_map: dict[int, str] = {}
        for kb in validated_kbs:
            kid = int(getattr(kb, "id", 0) or 0)
            if kid <= 0:
                continue
            label = (getattr(kb, "name", None) or "").strip() or f"KB#{kid}"
            kb_name_map[kid] = label

        # Calculate token budget / 计算 Token 预算
        builder = RAGContextBuilder(
            context_token_ratio=rag_config.get("context_token_ratio", 0.6),
        )

        # Estimate system prompt token count / 估算 system prompt 的 token 数
        system_tokens = estimate_tokens(messages[0].content) if messages else 0
        # Get actual context window size from associated AIModel / 从关联的 AIModel 获取实际上下文窗口大小
        model_context = 0
        if hasattr(agent, "model") and agent.model:
            model_context = getattr(agent.model, "context_window", 0) or 0
        max_context = model_context or 8000

        rag_budget, _ = builder.calculate_rag_budget(
            max_context_tokens=max_context,
            system_prompt_tokens=system_tokens,
            max_tokens=agent.max_tokens,
        )

        # Build RAG context / 构建 RAG 上下文
        rag_context = builder.build_rag_context(chunks, rag_budget, kb_names=kb_name_map)

        if not rag_context.rag_text:
            return messages, None

        # Inject into system message tail / 注入到 system 消息末尾
        if messages and messages[0].role == "system":
            messages[0] = ChatMessage(
                role="system",
                content=messages[0].content + "\n" + rag_context.rag_text,
            )

        # Build citation sources / 构建引用来源
        sources = [s.to_dict() for s in rag_context.sources]

        logger.info(
            "RAG injected: agent={}, chunks={}, tokens={}",
            agent.id, rag_context.chunk_count, rag_context.token_count,
        )

        return messages, sources

    except Exception as exc:
        logger.warning(
            "RAG injection failed for agent {}: {}",
            agent.id, str(exc),
        )
        return messages, None


__all__ = ["inject_rag_context", "load_agent_kb_bindings", "merge_kb_ids"]
