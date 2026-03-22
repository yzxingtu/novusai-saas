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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.routing.complexity_classifier import ComplexityClassifier, ComplexityLevel
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.ai import ModelTierEnum
from app.exceptions import BusinessException

if TYPE_CHECKING:
    from app.ai.types import ChatMessage
    from app.models.ai.agent import Agent
    from app.models.ai.model import AIModel
    from app.repositories.ai.model_repository import AIModelRepository

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


@dataclass
class RouteResult:
    """Routing result / 路由结果"""

    provider_code: str
    model_code: str
    model_id: int
    tier: str | None
    reason: str
    is_overridden: bool = False


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

        # ── 1. enable_routing=False → Directly return original model ──
        # ── 1. enable_routing=False → 直接返回原始模型 ──
        if not routing_config.get("enable_routing", False):
            return self._fallback(agent, reason="routing_disabled")

        # Extract request features from request / 从 request 提取请求特征
        messages: list[ChatMessage] = getattr(request, "messages", []) or []
        # Prioritize parsed tools from caller (_prepare_execution layer),
        # fall back to request.tools (compatible with old call paths)
        # 优先使用调用方传入的已解析 tools（_prepare_execution 层），
        # 回退到 request.tools（兼容旧调用路径）
        if tools is None:
            tools = getattr(request, "tools", None)
        has_attachments = self._detect_any_attachments(
            getattr(request, "attachments", None),
            messages,
        )

        # Detect if request contains image attachments (request-level + message-level)
        # 检测是否包含图片附件（request 级 + message 级）
        has_image_attachments = self._detect_image_attachments(
            getattr(request, "attachments", None), messages,
        )

        # Ensure agent's model is loaded / 确保 agent 的 model 已加载
        agent_model: AIModel | None = getattr(agent, "model", None)
        agent_provider_id: int | None = (
            agent_model.provider_id if agent_model else None
        )

        from app.repositories.ai.model_repository import AIModelRepository

        model_repo = AIModelRepository(self.db)

        has_audio, has_video = self._detect_audio_video_attachments(
            getattr(request, "attachments", None), messages,
        )
        needs_fc = bool(tools)

        # ── 2. Multimodal attachments → Requires matching capability set ──
        # ── 2. 多模态附件 → 需要满足对应能力组合 ──
        if has_image_attachments or has_audio or has_video:
            multimodal_result = await self._route_for_multimodal(
                routing_config=routing_config,
                agent=agent,
                agent_provider_id=agent_provider_id,
                model_repo=model_repo,
                has_image=has_image_attachments,
                has_audio=has_audio,
                has_video=has_video,
                needs_fc=needs_fc,
            )
            if multimodal_result:
                return multimodal_result
            raise BusinessException(
                message=_(self._get_multimodal_error_key(
                    has_image=has_image_attachments,
                    has_audio=has_audio,
                    has_video=has_video,
                )),
            )

        # ── 3. Long context → Requires large context_window ──
        # ── 3. 长上下文 → 需要大 context_window ──
        long_ctx_threshold: int = routing_config.get(
            "long_context_threshold", _DEFAULT_LONG_CONTEXT_THRESHOLD
        )
        requires_long_context = estimated_tokens > long_ctx_threshold
        if requires_long_context:
            long_ctx_result = await self._route_for_long_context(
                routing_config,
                agent,
                agent_provider_id,
                estimated_tokens,
                model_repo,
                needs_fc=needs_fc,
            )
            if long_ctx_result:
                return long_ctx_result

        # ── 4. ComplexityClassifier → tier ──
        complexity = self._classifier.classify(
            messages,
            tools,
            has_attachments=has_attachments or has_image_attachments or has_audio or has_video,
        )
        target_tiers = _TIER_CANDIDATES.get(complexity.value, [])

        # Apply max_tier limit / 应用 max_tier 限制
        max_tier = routing_config.get("max_tier")
        if max_tier:
            target_tiers = self._filter_tiers_by_max(target_tiers, max_tier)

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

        if requires_long_context and not self._model_satisfies_requirements(
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
        agent_provider_id: int | None = (
            agent_model.provider_id if agent_model else None
        )
        model_repo = AIModelRepository(self.db)
        result = await self._route_for_multimodal(
            routing_config=routing_config,
            agent=agent,
            agent_provider_id=agent_provider_id,
            model_repo=model_repo,
            has_image=has_image,
            has_audio=has_audio,
            has_video=has_video,
            needs_fc=needs_fc,
        )
        return result is not None

    async def _route_for_multimodal(
        self,
        routing_config: dict,
        agent: Agent,
        agent_provider_id: int | None,
        model_repo: AIModelRepository,
        *,
        has_image: bool,
        has_audio: bool,
        has_video: bool,
        needs_fc: bool,
    ) -> RouteResult | None:
        """
        Route requests that require one or more multimodal capabilities.
        为需要一种或多种多模态能力的请求选择模型。
        """
        agent_model: AIModel | None = getattr(agent, "model", None)
        if self._model_satisfies_requirements(
            agent_model,
            needs_vision=has_image,
            needs_audio=has_audio,
            needs_video=has_video,
            needs_fc=needs_fc,
        ) and await self._is_provider_healthy(getattr(agent_model, "provider_id", None)):
            return self._fallback(
                agent,
                reason=self._build_multimodal_reason(
                    has_image=has_image,
                    has_audio=has_audio,
                    has_video=has_video,
                    suffix="agent_model",
                ),
            )

        explicit_ids: list[int] = []
        vision_model_id: int | None = routing_config.get("vision_model_id")
        audio_model_id: int | None = routing_config.get("audio_model_id")
        video_model_id: int | None = routing_config.get("video_model_id")
        if has_video and video_model_id:
            explicit_ids.append(video_model_id)
        if has_audio and audio_model_id and audio_model_id not in explicit_ids:
            explicit_ids.append(audio_model_id)
        if has_image and vision_model_id and vision_model_id not in explicit_ids:
            explicit_ids.append(vision_model_id)

        for model_id_to_try in explicit_ids:
            model = await model_repo.get_active_with_provider(model_id_to_try)
            if (
                model
                and self._model_satisfies_requirements(
                    model,
                    needs_vision=has_image,
                    needs_audio=has_audio,
                    needs_video=has_video,
                    needs_fc=needs_fc,
                )
                and await self._is_provider_healthy(model.provider_id)
            ):
                return RouteResult(
                    provider_code=model.provider.code,
                    model_code=model.code,
                    model_id=model.id,
                    tier=model.tier,
                    reason=self._build_multimodal_reason(
                        has_image=has_image,
                        has_audio=has_audio,
                        has_video=has_video,
                        suffix="explicit_config",
                    ),
                    is_overridden=True,
                )

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
                supports_vision=has_image,
                supports_audio=has_audio,
                supports_video=has_video,
                supports_function_calling=needs_fc,
            )
            if model and await self._is_provider_healthy(model.provider_id):
                return RouteResult(
                    provider_code=model.provider.code,
                    model_code=model.code,
                    model_id=model.id,
                    tier=model.tier,
                    reason=self._build_multimodal_reason(
                        has_image=has_image,
                        has_audio=has_audio,
                        has_video=has_video,
                        suffix="tier_fallback",
                    ),
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
        *,
        needs_fc: bool,
    ) -> RouteResult | None:
        """Long context routing: prioritize explicitly configured long_context_model_id. / 长上下文路由：优先显式配置的 long_context_model_id。"""
        agent_model: AIModel | None = getattr(agent, "model", None)
        if self._model_satisfies_requirements(
            agent_model,
            min_context_window=estimated_tokens,
            needs_fc=needs_fc,
        ) and await self._is_provider_healthy(getattr(agent_model, "provider_id", None)):
            return self._fallback(agent, reason="long_context:agent_model")

        lc_model_id: int | None = routing_config.get("long_context_model_id")
        if lc_model_id:
            model = await model_repo.get_active_with_provider(lc_model_id)
            if (
                model
                and self._model_satisfies_requirements(
                    model,
                    min_context_window=estimated_tokens,
                    needs_fc=needs_fc,
                )
                and await self._is_provider_healthy(model.provider_id)
            ):
                return RouteResult(
                    provider_code=model.provider.code,
                    model_code=model.code,
                    model_id=model.id,
                    tier=model.tier,
                    reason="long_context:explicit_config",
                    is_overridden=True,
                )

        # Fallback: downgrade by tier to find models with larger context_window (limited by max_tier)
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
                supports_function_calling=needs_fc,
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

    # ==================== Helper Methods / 辅助方法 ====================

    @staticmethod
    def _model_satisfies_requirements(
        model: AIModel | None,
        *,
        needs_vision: bool = False,
        needs_audio: bool = False,
        needs_video: bool = False,
        needs_fc: bool = False,
        min_context_window: int | None = None,
    ) -> bool:
        """Check whether a model satisfies the required capability set. / 检查模型是否满足所需能力组合。"""
        if model is None:
            return False
        if needs_vision and not bool(getattr(model, "supports_vision", False)):
            return False
        if needs_audio and not bool(getattr(model, "supports_audio", False)):
            return False
        if needs_video and not bool(getattr(model, "supports_video", False)):
            return False
        if needs_fc and not bool(getattr(model, "supports_function_calling", False)):
            return False
        if min_context_window is not None:
            context_window = int(getattr(model, "context_window", 0) or 0)
            if context_window < min_context_window:
                return False
        return True

    @staticmethod
    def _build_multimodal_reason(
        *,
        has_image: bool,
        has_audio: bool,
        has_video: bool,
        suffix: str,
    ) -> str:
        parts: list[str] = []
        if has_image:
            parts.append("vision")
        if has_audio:
            parts.append("audio")
        if has_video:
            parts.append("video")
        if not parts:
            parts.append("multimodal")
        return ":".join(parts + [suffix])

    @staticmethod
    def _get_multimodal_error_key(
        *,
        has_image: bool,
        has_audio: bool,
        has_video: bool,
    ) -> str:
        if has_image and not has_audio and not has_video:
            return "agent_chat.error.no_vision_model_available"
        if has_audio and has_video and not has_image:
            return "agent_chat.error.no_audio_video_model_available"
        if has_audio and not has_image and not has_video:
            return "agent_chat.error.no_audio_model_available"
        if has_video and not has_image and not has_audio:
            return "agent_chat.error.no_video_model_available"
        return "agent_chat.error.no_multimodal_model_available"

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

    @staticmethod
    def _detect_image_attachments(
        request_attachments: list[dict[str, Any]] | None,
        messages: list[ChatMessage],
    ) -> bool:
        """
        检测请求中是否包含图片附件（request 级 + message 级）/ Detect if request contains image attachments (request-level + message-level).

        Args:
            request_attachments: ExecutionRequest.attachments
            messages: List of messages (may contain message.attachments)
                      消息列表（可能含 message.attachments）

        Returns:
            True if any image attachment found
        """
        # Check request-level attachments / 检查 request 级附件
        if request_attachments:
            for att in request_attachments:
                if isinstance(att, dict) and att.get("type") == "image":
                    return True

        # Check message-level attachments (frontend directly injects into ChatMessage.attachments)
        # 检查 message 级附件（前端直接注入到 ChatMessage.attachments）
        for msg in messages:
            if msg.attachments:
                for att in msg.attachments:
                    if isinstance(att, dict) and att.get("type") == "image":
                        return True

        return False

    @staticmethod
    def _detect_any_attachments(
        request_attachments: list[dict[str, Any]] | None,
        messages: list[ChatMessage],
    ) -> bool:
        """
        Detect whether the request contains any attachment, including message-level files.
        检测请求是否包含任意附件，包括消息级文件附件。
        """
        if request_attachments:
            return True
        return any(bool(getattr(msg, "attachments", None)) for msg in messages)

    @staticmethod
    def _detect_audio_video_attachments(
        request_attachments: list[dict[str, Any]] | None,
        messages: list[ChatMessage],
    ) -> tuple[bool, bool]:
        """
        检测请求中是否包含音频/视频附件（request 级 + message 级）。
        Detect if request contains audio/video attachments (request-level + message-level).

        Returns:
            (has_audio, has_video)
        """
        has_audio = False
        has_video = False

        def check_att(att: dict[str, Any]) -> None:
            nonlocal has_audio, has_video
            t = att.get("type") if isinstance(att, dict) else None
            if t == "audio":
                has_audio = True
            elif t == "video":
                has_video = True

        if request_attachments:
            for att in request_attachments:
                check_att(att)
        for msg in messages:
            if msg.attachments:
                for att in msg.attachments:
                    check_att(att)

        return has_audio, has_video

    @staticmethod
    def _filter_tiers_by_max(tiers: list[str], max_tier: str) -> list[str]:
        """
        按 max_tier 过滤，只保留不超过 max_tier 级别的 tier / Filter by max_tier, keeping only tiers not exceeding max_tier level.

        Level order: fast < standard < premium
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
