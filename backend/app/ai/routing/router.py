"""
ModelRouter — AI 多模型路由引擎

路由优先级（从高到低）：
1. routing_config.enable_routing=False → 直接返回 agent 原始 provider+model（向后兼容）
2. 有图片附件 → 优先 vision_model_id，否则按 tier 查找 vision 模型（受 max_tier 限制）
3. 有工具且目标模型不支持 FC → 升级到同 tier 内支持 FC 的模型
4. estimated_tokens > long_context_threshold → 优先 long_context_model_id，否则按 tier 降级找大 context_window 模型（受 max_tier 限制）
5. ComplexityClassifier 分类 → 映射到 tier
6. 按 tier 从 DB 查询模型（同 provider 优先 + 价格 ASC）
7. Provider 健康检查 → 不健康则降 tier
8. 兜底 agent.model_id（永远不失败）

routing_config 字段（T4 迁移后生效，此处通过 getattr 安全访问）：
- enable_routing: bool  — 是否启用多模型路由
- max_tier: str | None  — 最大允许 tier（防止意外使用 premium）
- vision_model_id: int | None
- long_context_model_id: int | None
- long_context_threshold: int — token 数量触发阈值
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.routing.complexity_classifier import ComplexityClassifier, ComplexityLevel
from app.core.logging import LogManager
from app.enums.ai import ModelTierEnum

if TYPE_CHECKING:
    from app.ai.types import ChatMessage
    from app.models.ai.agent import Agent
    from app.models.ai.model import AIModel
    from app.repositories.ai.model_repository import AIModelRepository

logger = LogManager.get_logger("ai.routing")

# Tier 降级顺序
_TIER_CANDIDATES: dict[str, list[str]] = {
    ComplexityLevel.COMPLEX.value: [
        ModelTierEnum.PREMIUM.value,
        ModelTierEnum.STANDARD.value,
        ModelTierEnum.FAST.value,
    ],
    ComplexityLevel.MEDIUM.value: [
        ModelTierEnum.STANDARD.value,
        ModelTierEnum.PREMIUM.value,
        ModelTierEnum.FAST.value,
    ],
    ComplexityLevel.SIMPLE.value: [
        ModelTierEnum.FAST.value,
        ModelTierEnum.STANDARD.value,
        ModelTierEnum.PREMIUM.value,
    ],
}

# 默认长上下文阈值（tokens）
_DEFAULT_LONG_CONTEXT_THRESHOLD = 32_000


@dataclass
class RouteResult:
    """路由结果"""

    provider_code: str
    model_code: str
    model_id: int
    tier: str | None
    reason: str
    is_overridden: bool = False


class ModelRouter:
    """
    AI 多模型路由引擎

    根据请求特征（复杂度、附件、工具、Token 数量）选择最合适的 AI 模型。
    任何异常或找不到模型时自动兜底到 agent.model_id，不抛出异常。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._classifier = ComplexityClassifier()

    async def route(
        self,
        agent: Agent,
        request: Any,
        estimated_tokens: int = 0,
    ) -> RouteResult:
        """
        执行路由，返回选择的模型信息

        Args:
            agent: 智能体对象（含 model_id / model 关系）
            request: 执行请求（支持 messages/tools/has_attachments 属性）
            estimated_tokens: 估算 Token 数（用于长上下文判断）

        Returns:
            RouteResult（永远不 None，失败时返回 agent 原始模型）
        """
        try:
            return await self._do_route(agent, request, estimated_tokens)
        except Exception as exc:
            logger.warning(
                "ModelRouter.route failed (agent_id=%s): %s — falling back to agent model",
                getattr(agent, "id", "?"),
                str(exc),
            )
            return self._fallback(agent, reason=f"exception: {exc}")

    # ==================== 核心路由逻辑 ====================

    async def _do_route(
        self,
        agent: Agent,
        request: Any,
        estimated_tokens: int,
    ) -> RouteResult:
        routing_config: dict = getattr(agent, "routing_config", None) or {}

        # ── 1. enable_routing=False → 直接返回原始模型 ──
        if not routing_config.get("enable_routing", False):
            return self._fallback(agent, reason="routing_disabled")

        # 从 request 提取请求特征
        messages: list[ChatMessage] = getattr(request, "messages", []) or []
        tools: list | None = getattr(request, "tools", None)
        has_attachments: bool = bool(getattr(request, "attachments", None))

        # 检测是否包含图片附件（request 级 + message 级）
        has_image_attachments = self._detect_image_attachments(
            getattr(request, "attachments", None), messages,
        )

        # 确保 agent 的 model 已加载
        agent_model: AIModel | None = getattr(agent, "model", None)
        agent_provider_id: int | None = (
            agent_model.provider_id if agent_model else None
        )

        from app.repositories.ai.model_repository import AIModelRepository

        model_repo = AIModelRepository(self.db)

        # ── 2. 图片附件 → 需要 Vision 能力 ──
        if has_image_attachments:
            vision_result = await self._route_for_vision(
                routing_config, agent, agent_provider_id, model_repo
            )
            if vision_result:
                return vision_result

        # ── 3. 长上下文 → 需要大 context_window ──
        long_ctx_threshold: int = routing_config.get(
            "long_context_threshold", _DEFAULT_LONG_CONTEXT_THRESHOLD
        )
        if estimated_tokens > long_ctx_threshold:
            long_ctx_result = await self._route_for_long_context(
                routing_config, agent, agent_provider_id, estimated_tokens, model_repo
            )
            if long_ctx_result:
                return long_ctx_result

        # ── 4. ComplexityClassifier → tier ──
        complexity = self._classifier.classify(
            messages, tools, has_attachments=has_attachments or has_image_attachments
        )
        target_tiers = _TIER_CANDIDATES.get(complexity.value, [])

        # 应用 max_tier 限制
        max_tier = routing_config.get("max_tier")
        if max_tier:
            target_tiers = self._filter_tiers_by_max(target_tiers, max_tier)

        needs_fc = bool(tools)

        for tier in target_tiers:
            model = await model_repo.get_by_tier(
                tier=tier,
                preferred_provider_id=agent_provider_id,
                supports_function_calling=needs_fc,
            )
            if not model:
                continue

            # ── 5. Provider 健康检查 ──
            if not await self._is_provider_healthy(model.provider_id):
                logger.warning(
                    "ModelRouter: provider %d unhealthy for tier=%s, trying next tier",
                    model.provider_id,
                    tier,
                )
                continue

            return RouteResult(
                provider_code=model.provider.code,
                model_code=model.code,
                model_id=model.id,
                tier=tier,
                reason=f"complexity:{complexity.value}",
                is_overridden=True,
            )

        # ── 6. 兜底 ──
        return self._fallback(agent, reason="no_tier_model_found")

    # ==================== 子路由方法 ====================

    async def _route_for_vision(
        self,
        routing_config: dict,
        agent: Agent,
        agent_provider_id: int | None,
        model_repo: AIModelRepository,
    ) -> RouteResult | None:
        """图片路由：优先显式配置的 vision_model_id"""
        _ = agent

        vision_model_id: int | None = routing_config.get("vision_model_id")
        if vision_model_id:
            model = await model_repo.get_active_with_provider(vision_model_id)
            if (
                model
                and getattr(model, "supports_vision", False)
                and await self._is_provider_healthy(model.provider_id)
            ):
                return RouteResult(
                    provider_code=model.provider.code,
                    model_code=model.code,
                    model_id=model.id,
                    tier=model.tier,
                    reason="vision:explicit_config",
                    is_overridden=True,
                )

        # 退而求其次：按 tier 找 vision 模型（受 max_tier 限制）
        fallback_tiers = [
            ModelTierEnum.STANDARD.value,
            ModelTierEnum.PREMIUM.value,
            ModelTierEnum.FAST.value,
        ]
        max_tier = routing_config.get("max_tier")
        if max_tier:
            fallback_tiers = self._filter_tiers_by_max(fallback_tiers, max_tier)

        for tier in fallback_tiers:
            model = await model_repo.get_by_tier(
                tier=tier,
                preferred_provider_id=agent_provider_id,
                supports_vision=True,
            )
            if model and await self._is_provider_healthy(model.provider_id):
                return RouteResult(
                    provider_code=model.provider.code,
                    model_code=model.code,
                    model_id=model.id,
                    tier=model.tier,
                    reason="vision:tier_fallback",
                    is_overridden=True,
                )

        return None

    async def _route_for_long_context(
        self,
        routing_config: dict,
        agent: Agent,
        agent_provider_id: int | None,
        estimated_tokens: int,
        model_repo: AIModelRepository,
    ) -> RouteResult | None:
        """长上下文路由：优先显式配置的 long_context_model_id"""
        _ = agent

        lc_model_id: int | None = routing_config.get("long_context_model_id")
        if lc_model_id:
            model = await model_repo.get_active_with_provider(lc_model_id)
            if model and await self._is_provider_healthy(model.provider_id):
                return RouteResult(
                    provider_code=model.provider.code,
                    model_code=model.code,
                    model_id=model.id,
                    tier=model.tier,
                    reason="long_context:explicit_config",
                    is_overridden=True,
                )

        # 退而求其次：按 tier 降级找大 context_window 模型（受 max_tier 限制）
        fallback_tiers = [
            ModelTierEnum.PREMIUM.value,
            ModelTierEnum.STANDARD.value,
            ModelTierEnum.FAST.value,
        ]
        max_tier = routing_config.get("max_tier")
        if max_tier:
            fallback_tiers = self._filter_tiers_by_max(fallback_tiers, max_tier)

        for tier in fallback_tiers:
            model = await model_repo.get_by_tier(
                tier=tier,
                preferred_provider_id=agent_provider_id,
                min_context_window=estimated_tokens,
            )
            if model and await self._is_provider_healthy(model.provider_id):
                return RouteResult(
                    provider_code=model.provider.code,
                    model_code=model.code,
                    model_id=model.id,
                    tier=model.tier,
                    reason="long_context:tier_fallback",
                    is_overridden=True,
                )

        return None

    # ==================== 辅助方法 ====================

    @staticmethod
    def _fallback(agent: Agent, reason: str) -> RouteResult:
        """兜底：使用 agent 原始配置的模型"""
        model: AIModel | None = getattr(agent, "model", None)
        provider = getattr(model, "provider", None) if model else None

        provider_code: str = getattr(provider, "code", "") if provider else ""
        model_code: str = getattr(model, "code", "") if model else ""
        model_id: int = getattr(agent, "model_id", 0)
        model_tier: str | None = getattr(model, "tier", None) if model else None

        logger.debug(
            "ModelRouter fallback: agent_id=%s reason=%s model_id=%s",
            getattr(agent, "id", "?"),
            reason,
            model_id,
        )

        return RouteResult(
            provider_code=provider_code,
            model_code=model_code,
            model_id=model_id,
            tier=model_tier,
            reason=reason,
            is_overridden=False,
        )

    async def _is_provider_healthy(self, provider_id: int | None) -> bool:
        """检查供应商健康状态（失败时默认健康，避免误屏蔽）"""
        if not provider_id:
            return True
        try:
            from app.ai.failover import FailoverService

            failover = FailoverService(self.db)
            return await failover.is_provider_healthy(provider_id)
        except Exception as exc:
            logger.warning("ModelRouter health check failed: %s", str(exc))
            return True

    @staticmethod
    def _detect_image_attachments(
        request_attachments: list[dict[str, Any]] | None,
        messages: list[ChatMessage],
    ) -> bool:
        """
        检测请求中是否包含图片附件（request 级 + message 级）

        Args:
            request_attachments: ExecutionRequest.attachments
            messages: 消息列表（可能含 message.attachments）

        Returns:
            True if any image attachment found
        """
        # 检查 request 级附件
        if request_attachments:
            for att in request_attachments:
                if isinstance(att, dict) and att.get("type") == "image":
                    return True

        # 检查 message 级附件（前端直接注入到 ChatMessage.attachments）
        for msg in messages:
            if msg.attachments:
                for att in msg.attachments:
                    if isinstance(att, dict) and att.get("type") == "image":
                        return True

        return False

    @staticmethod
    def _filter_tiers_by_max(tiers: list[str], max_tier: str) -> list[str]:
        """
        按 max_tier 过滤，只保留不超过 max_tier 级别的 tier

        级别顺序：fast < standard < premium
        """
        order = [
            ModelTierEnum.FAST.value,
            ModelTierEnum.STANDARD.value,
            ModelTierEnum.PREMIUM.value,
        ]
        try:
            max_index = order.index(max_tier)
        except ValueError:
            return tiers
        return [t for t in tiers if t in order and order.index(t) <= max_index]


__all__ = ["ModelRouter", "RouteResult"]
