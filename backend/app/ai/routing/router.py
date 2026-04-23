"""
ModelRouter — AI Multi-Model Routing Engine / AI 多模型路由引擎

Routing priority (high to low) / 路由优先级（从高到低）：
1. routing_config.enable_routing=False → Directly return agent's original provider+model (backward compatible)
   routing_config.enable_routing=False → 直接返回 agent 原始 provider+model（向后兼容）
2. Has modality-sensitive attachments → Prioritize capability-matched model, otherwise find a capable tier fallback
   有能力敏感附件 → 优先匹配能力的模型，否则按 tier 查找可用兜底模型
3. Has tools and target model doesn't support FC → Upgrade to FC-capable model in same tier
   有工具且目标模型不支持 FC → 升级到同 tier 内支持 FC 的模型
4. estimated_tokens > long_context_threshold → Prioritize long_context_model_id, otherwise downgrade by tier for larger context_window (limited by max_tier)
   estimated_tokens > long_context_threshold → 优先 long_context_model_id，否则按 tier 降级找大 context_window 模型（受 max_tier 限制）
5. ComplexityClassifier classification → Map to tier / ComplexityClassifier 分类 → 映射到 tier
6. Query model from DB by tier (same provider first + price ASC)
   按 tier 从 DB 查询模型（同 provider 优先 + 价格 ASC）
7. Provider health check → Downgrade tier if unhealthy / Provider 健康检查 → 不健康则降 tier
8. Fallback to agent.model_id when routing has no better option
   当路由没有更优模型时兜底回 agent.model_id

routing_config fields (effective after T4 migration, accessed safely via getattr here)
routing_config 字段（T4 迁移后生效，此处通过 getattr 安全访问）：
- enable_routing: bool — Whether to enable multi-model routing / 是否启用多模型路由
- max_tier: str | None — Max allowed tier (prevent accidental premium use) / 最大允许 tier（防止意外使用 premium）
- vision_model_id: int | None
- long_context_model_id: int | None
- long_context_threshold: int — Token count trigger threshold / token 数量触发阈值
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.routing.complexity_classifier import ComplexityClassifier, ComplexityLevel
from app.ai.routing.routing_capabilities import (
    detect_any_attachments,
    detect_audio_video_attachments,
    detect_image_attachments,
    model_satisfies_requirements,
)
from app.ai.routing.routing_contracts import RouteResult
from app.ai.routing.routing_helpers import (
    filter_tiers_by_max,
    get_multimodal_error_key,
)
from app.ai.routing.routing_selection import (
    route_for_long_context,
    route_for_multimodal,
)
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import ModelTierEnum
from app.exceptions import BusinessException

if TYPE_CHECKING:
    from app.ai.types import ChatMessage
    from app.models.ai.agent import Agent
    from app.models.ai.model import AIModel

logger = LogManager.get_logger("ai.routing")

# Tier downgrade order / Tier 降级顺序
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

# Default long context threshold (tokens) / 默认长上下文阈值（tokens）
_DEFAULT_LONG_CONTEXT_THRESHOLD = 32_000


class ModelRouter:
    """
    AI Multi-Model Routing Engine / AI 多模型路由引擎。

    Selects the most suitable AI model based on request characteristics (complexity, attachments, tools, token count).
    Falls back to agent.model_id on internal routing failures or missing tier matches.
    Raises BusinessException when the request requires capabilities or context window that no model can satisfy.
    根据请求特征（复杂度、附件、工具、Token 数量）选择最合适的 AI 模型。
    内部路由失败或找不到合适 tier 时会自动兜底到 agent.model_id。
    但当请求明确要求的能力或上下文窗口没有任何模型可满足时，会抛出 BusinessException。
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._classifier = ComplexityClassifier()

    async def route(
        self,
        agent: Agent,
        request: Any,
        estimated_tokens: int = 0,
        tools: list | None = None,
    ) -> RouteResult:
        """
        Execute routing and return selected model information
        执行路由，返回选择的模型信息

        Args:
            agent: Agent object (contains model_id / model relationship)
                   智能体对象（含 model_id / model 关系）
            request: Execution request (supports messages/attachments properties)
                     执行请求（支持 messages/attachments 属性）
            estimated_tokens: Estimated token count (for long context determination)
                              估算 Token 数（用于长上下文判断）
            tools: List of parsed tools (for FC capability routing and complexity scoring)
                   已解析的工具列表（用于 FC 能力路由和复杂度评分）

        Returns:
            RouteResult（永远不为 None；内部失败时回退到 agent 原始模型）

        Raises:
            BusinessException: Required modality or context window cannot be satisfied.
            BusinessException：必需的多模态能力或上下文窗口没有可用模型可满足。
        """
        try:
            return await self._do_route(agent, request, estimated_tokens, tools)
        except BusinessException:
            raise
        except Exception as exc:
            logger.warning(
                "ModelRouter.route failed (agent_id={}): {} — falling back to agent model",
                getattr(agent, "id", "?"),
                str(exc),
            )
            return self._fallback(agent, reason=f"exception: {exc}")

    # ==================== Core Routing Logic / 核心路由逻辑 ====================

    async def _do_route(
        self,
        agent: Agent,
        request: Any,
        estimated_tokens: int,
        tools: list | None = None,
    ) -> RouteResult:
        routing_config: dict = getattr(agent, "routing_config", None) or {}

        # Extract request features from request / 从 request 提取请求特征
        messages: list[ChatMessage] = getattr(request, "messages", []) or []
        has_attachments = detect_any_attachments(
            getattr(request, "attachments", None),
            messages,
        )

        # Detect if request contains image attachments (request-level + message-level)
        # 检测是否包含图片附件（request 级 + message 级）
        has_image_attachments = detect_image_attachments(
            getattr(request, "attachments", None),
            messages,
        )

        # Ensure agent's model is loaded / 确保 agent 的 model 已加载
        agent_model: AIModel | None = getattr(agent, "model", None)
        agent_provider_id: int | None = agent_model.provider_id if agent_model else None

        from app.repositories.ai.model_repository import AIModelRepository

        model_repo = AIModelRepository(self.db)

        has_audio, has_video = detect_audio_video_attachments(
            getattr(request, "attachments", None),
            messages,
        )
        needs_fc = bool(tools)

        # ── 1. enable_routing=False → Prefer original model unless provider is unhealthy ──
        # ── 1. enable_routing=False → 优先原模型，除非当前供应商已不健康 ──
        if not routing_config.get("enable_routing", False):
            unhealthy_fallback = await self._route_disabled_routing_provider_failover(
                agent=agent,
                has_image_attachments=has_image_attachments,
                has_audio=has_audio,
                has_video=has_video,
                needs_fc=needs_fc,
                estimated_tokens=estimated_tokens,
                long_ctx_threshold=routing_config.get(
                    "long_context_threshold",
                    _DEFAULT_LONG_CONTEXT_THRESHOLD,
                ),
            )
            if unhealthy_fallback is not None:
                return unhealthy_fallback
            return self._fallback(agent, reason="routing_disabled")

        # ── 2. Multimodal attachments → Requires matching capability set ──
        # ── 2. 多模态附件 → 需要满足对应能力组合 ──
        if has_image_attachments or has_audio or has_video:
            multimodal_result = await route_for_multimodal(
                routing_config=routing_config,
                agent=agent,
                agent_provider_id=agent_provider_id,
                model_repo=model_repo,
                has_image=has_image_attachments,
                has_audio=has_audio,
                has_video=has_video,
                needs_fc=needs_fc,
                fallback=self._fallback,
                is_provider_healthy=self._is_provider_healthy,
            )
            if multimodal_result:
                return multimodal_result
            raise BusinessException(
                message=_(
                    get_multimodal_error_key(
                        has_image=has_image_attachments,
                        has_audio=has_audio,
                        has_video=has_video,
                    )
                ),
            )

        # ── 3. Long context → Requires large context_window ──
        # ── 3. 长上下文 → 需要大 context_window ──
        long_ctx_threshold: int = routing_config.get(
            "long_context_threshold", _DEFAULT_LONG_CONTEXT_THRESHOLD
        )
        requires_long_context = estimated_tokens > long_ctx_threshold
        if requires_long_context:
            long_ctx_result = await route_for_long_context(
                routing_config=routing_config,
                agent=agent,
                agent_provider_id=agent_provider_id,
                estimated_tokens=estimated_tokens,
                model_repo=model_repo,
                needs_fc=needs_fc,
                fallback=self._fallback,
                is_provider_healthy=self._is_provider_healthy,
            )
            if long_ctx_result:
                return long_ctx_result

        # ── 4. ComplexityClassifier → tier ── / 4. 复杂度分类 → tier
        complexity = self._classifier.classify(
            messages,
            tools,
            has_attachments=has_attachments
            or has_image_attachments
            or has_audio
            or has_video,
        )
        target_tiers = _TIER_CANDIDATES.get(complexity.value, [])

        # Apply max_tier limit / 应用 max_tier 限制
        max_tier = routing_config.get("max_tier")
        if max_tier:
            target_tiers = filter_tiers_by_max(target_tiers, max_tier)

        min_context_window = estimated_tokens if requires_long_context else None

        for tier in target_tiers:
            model = await model_repo.get_by_tier(
                tier=tier,
                preferred_provider_id=agent_provider_id,
                supports_function_calling=needs_fc,
                min_context_window=min_context_window,
            )
            if not model:
                continue

            # ── 5. Provider health check ──
            # ── 5. Provider 健康检查 ──
            if not await self._is_provider_healthy(model.provider_id):
                logger.warning(
                    "ModelRouter: provider {} unhealthy for tier={}, trying next tier",
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

        if requires_long_context and not model_satisfies_requirements(
            agent_model,
            min_context_window=estimated_tokens,
            needs_fc=needs_fc,
        ):
            raise BusinessException(
                message=_("agent_chat.error.no_long_context_model_available"),
            )

        # ── 6. Fallback ──
        # ── 6. 兜底 ──
        return self._fallback(agent, reason="no_tier_model_found")

    # ==================== Sub-Routing Methods / 子路由方法 ====================

    async def can_handle_attachments(
        self,
        agent: Agent,
        *,
        has_image: bool = False,
        has_audio: bool = False,
        has_video: bool = False,
        needs_fc: bool = False,
    ) -> bool:
        """
        Check whether the agent can satisfy requested multimodal capabilities.
        检查智能体是否能满足当前多模态能力要求。
        """
        if not (has_image or has_audio or has_video):
            return True

        from app.repositories.ai.model_repository import AIModelRepository

        routing_config: dict = getattr(agent, "routing_config", None) or {}
        agent_model: AIModel | None = getattr(agent, "model", None)
        if not routing_config.get("enable_routing", False):
            return model_satisfies_requirements(
                agent_model,
                needs_vision=has_image,
                needs_audio=has_audio,
                needs_video=has_video,
                needs_fc=needs_fc,
            )
        agent_provider_id: int | None = agent_model.provider_id if agent_model else None
        model_repo = AIModelRepository(self.db)
        result = await route_for_multimodal(
            routing_config=routing_config,
            agent=agent,
            agent_provider_id=agent_provider_id,
            model_repo=model_repo,
            has_image=has_image,
            has_audio=has_audio,
            has_video=has_video,
            needs_fc=needs_fc,
            fallback=self._fallback,
            is_provider_healthy=self._is_provider_healthy,
        )
        return result is not None

    async def _route_disabled_routing_provider_failover(
        self,
        *,
        agent: Agent,
        has_image_attachments: bool,
        has_audio: bool,
        has_video: bool,
        needs_fc: bool,
        estimated_tokens: int,
        long_ctx_threshold: int,
    ) -> RouteResult | None:
        agent_model: AIModel | None = getattr(agent, "model", None)
        provider_id = getattr(agent_model, "provider_id", None)
        if not provider_id or await self._is_provider_healthy(provider_id):
            return None

        min_context_window = (
            estimated_tokens if estimated_tokens > long_ctx_threshold else None
        )

        try:
            from app.ai.failover import FailoverService

            fallback_model = await FailoverService(self.db).get_fallback_model(
                getattr(agent, "model_id", 0),
                needs_vision=has_image_attachments,
                needs_audio=has_audio,
                needs_video=has_video,
                needs_fc=needs_fc,
                min_context_window=min_context_window,
            )
        except Exception as exc:
            logger.warning(
                "ModelRouter disabled-routing failover failed: agent_id={} error={}",
                getattr(agent, "id", None),
                str(exc),
            )
            return None

        if fallback_model is None:
            return None

        logger.info(
            "ModelRouter disabled-routing failover: agent_id={} original_model_id={} fallback_model_id={}",
            getattr(agent, "id", None),
            getattr(agent, "model_id", None),
            fallback_model.id,
        )
        return RouteResult(
            provider_code=fallback_model.provider.code,
            model_code=fallback_model.code,
            model_id=fallback_model.id,
            tier=getattr(fallback_model, "tier", None),
            reason="provider_unhealthy:auto_failover",
            is_overridden=True,
        )

    @staticmethod
    def _fallback(agent: Agent, reason: str) -> RouteResult:
        """Fallback: use agent's original configured model / 兜底：使用 agent 原始配置的模型"""
        model: AIModel | None = getattr(agent, "model", None)
        provider = getattr(model, "provider", None) if model else None

        provider_code: str = getattr(provider, "code", "") if provider else ""
        model_code: str = getattr(model, "code", "") if model else ""
        model_id: int = getattr(agent, "model_id", 0)
        model_tier: str | None = getattr(model, "tier", None) if model else None

        logger.debug(
            "ModelRouter fallback: agent_id={} reason={} model_id={}",
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
        """Check provider health status (defaults to healthy on failure to avoid false blocking). / 检查供应商健康状态（失败时默认健康，避免误屏蔽）。"""
        if not provider_id:
            return True
        try:
            from app.ai.failover import FailoverService

            failover = FailoverService(self.db)
            return await failover.is_provider_healthy(provider_id)
        except Exception as exc:
            logger.warning("ModelRouter health check failed: {}", str(exc))
            return True


__all__ = ["ModelRouter", "RouteResult"]
