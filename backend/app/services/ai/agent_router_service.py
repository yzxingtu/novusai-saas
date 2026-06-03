"""
智能体路由服务 / Agent Router Service

根据用户消息、附件类型和当前对话，通过 Router 智能体智能选择最合适的目标智能体。
Selects the most suitable target agent via Router agent based on user messages,
attachments, and conversation state.
候选过滤遵循平台分发、企业发布和端内访问控制的新语义。
Candidate filtering follows the new platform distribution, tenant publication,
and endpoint-internal access semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException
from app.models.ai.agent import Agent
from app.models.system.agent_assignment import SystemAgentAssignment
from app.services.ai.agent_router_candidate_support import filter_router_candidates
from app.services.ai.agent_router_capability_support import (
    agent_can_handle_images,
    agent_supports_executable_families,
)
from app.services.ai.agent_router_query_service import AgentRouterQueryService
from app.services.ai.agent_router_runtime_support import (
    ROUTER_TIMEOUT_SECONDS,
    AgentRouterRuntimeSupport,
)

logger = LogManager.get_logger("ai")

# Routing method constants / 路由方式常量
ROUTED_BY_PINNED = "pinned"
ROUTED_BY_ROUTER = "router"
ROUTED_BY_DEFAULT = "default"
ROUTED_BY_PREFERRED_FALLBACK = "preferred_fallback"
ROUTED_BY_CONVERSATION = "conversation"

# Minimum confidence threshold / 最低置信度阈值
MIN_CONFIDENCE_THRESHOLD = 0.3


@dataclass
class RouteResult:
    """路由结果 / Route result."""

    agent_id: int
    agent_name: str
    confidence: float
    routed_by: str


class AgentRouterService:
    """
    智能体路由服务 / Agent router service.

    流程:
    1. pinned_agent_id 直通（用户手动选择）
    2. 构建当前调用方可见的候选列表
    3. 获取 Router 智能体，TASK 模式调用
    4. 解析 JSON 结果，二次 valid_ids 校验
    5. 降级到 default_chat

    降级策略:
    - Router 未找到 → default_chat
    - Router 未配置模型 → default_chat
    - Router 超时 → default_chat
    - 低置信度 → default_chat
    - default_chat 未配置 → 返回错误
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._query_service = AgentRouterQueryService(db)
        self._runtime_support = AgentRouterRuntimeSupport(db)

    @property
    def query_service(self) -> AgentRouterQueryService:
        if not hasattr(self, "_query_service"):
            self._query_service = AgentRouterQueryService(self.db)
        return self._query_service

    @property
    def runtime_support(self) -> AgentRouterRuntimeSupport:
        if not hasattr(self, "_runtime_support"):
            self._runtime_support = AgentRouterRuntimeSupport(self.db)
        return self._runtime_support

    async def route(
        self,
        tenant_id: int | None,
        message: str,
        conversation_id: int | None = None,
        pinned_agent_id: int | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        user_id: int | None = None,
        force_reroute: bool = False,
        has_image_attachments: bool = False,
        has_audio_attachments: bool = False,
        has_video_attachments: bool = False,
        has_file_attachments: bool = False,
    ) -> RouteResult:
        """
        执行智能路由 / Execute agent routing.

        Args：
            tenant_id: 企业 ID（管理端可为 None）
            message: 用户消息
            conversation_id: 已有对话 ID（若存在且未 force_reroute，则沿用当前对话绑定智能体）
            pinned_agent_id: 用户固定选择的智能体 ID
            user_role: 调用方角色（UserRoleEnum 值），用于候选列表过滤

        Returns：
            RouteResult 路由结果
        """
        if conversation_id and not force_reroute:
            conversation = await self._get_accessible_conversation(
                conversation_id,
                tenant_id,
                user_role,
                user_id=user_id,
            )
            agent = await self._get_published_agent(conversation.agent_id)
            if agent and await self._is_agent_visible(
                agent,
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
            ):
                if has_image_attachments:
                    await self._ensure_agent_supports_images(
                        agent,
                        error_key="agent_chat.error.conversation_agent_not_vision",
                    )
                return RouteResult(
                    agent_id=agent.id,
                    agent_name=agent.name,
                    confidence=1.0,
                    routed_by=ROUTED_BY_CONVERSATION,
                )

            logger.warning(
                "Conversation-bound agent {} unavailable for conversation={} tenant={} role={}",
                conversation.agent_id,
                conversation_id,
                tenant_id,
                user_role,
            )
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
            )

        # P1: pinned agent short-circuit / P1：pinned 智能体直通
        if pinned_agent_id:
            agent = await self._get_published_agent(pinned_agent_id)
            if agent:
                if await self._is_agent_visible(
                    agent,
                    tenant_id,
                    user_role,
                    user_id=user_id,
                    user_role_id=user_role_id,
                ):
                    if has_image_attachments:
                        await self._ensure_agent_supports_images(
                            agent,
                            error_key="agent_chat.error.pinned_agent_not_vision",
                        )
                    return RouteResult(
                        agent_id=agent.id,
                        agent_name=agent.name,
                        confidence=1.0,
                        routed_by=ROUTED_BY_PINNED,
                    )
                logger.warning(
                    "Pinned agent {} not accessible for tenant={} user_role={}",
                    pinned_agent_id,
                    tenant_id,
                    user_role,
                )

        # P2: Build candidate pool / 构建候选列表
        candidates = await self._list_available_agents(
            tenant_id,
            user_role,
            user_id=user_id,
            user_role_id=user_role_id,
        )
        if not candidates:
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
            )

        filter_result = await filter_router_candidates(
            message=message,
            candidates=candidates,
            has_image_attachments=has_image_attachments,
            agent_can_handle_images=self._agent_can_handle_images,
            agent_supports_families_fn=lambda agent, families: (
                self._agent_supports_families(
                    agent,
                    families,
                    tenant_id=(
                        PLATFORM_TENANT_ID
                        if user_role == UserRoleEnum.PLATFORM_ADMIN.value
                        else tenant_id
                    ),
                )
            ),
        )
        candidates = filter_result.candidates

        if filter_result.direct_selected_agent:
            agent = filter_result.direct_selected_agent
            logger.info(
                "Agent router: directly selected preferred agent {} ({})",
                agent.id,
                agent.name,
            )
            return RouteResult(
                agent_id=agent.id,
                agent_name=agent.name,
                confidence=1.0,
                routed_by=ROUTED_BY_ROUTER,
            )

        valid_ids = {a.id for a in candidates}
        preferred_fallback_candidates = filter_result.preferred_fallback_candidates

        # P3: Resolve router agent / 获取 Router 智能体
        router_agent = await self._get_router_agent()
        if not router_agent:
            logger.warning("Router agent not found, falling back to default")
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
                preferred_candidates=preferred_fallback_candidates,
            )

        if not router_agent.model_id:
            logger.warning("Router agent model not configured")
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
                preferred_candidates=preferred_fallback_candidates,
            )

        # P3.5: Call router agent in TASK mode / 调用 Router 智能体（TASK 模式）
        try:
            route_result = await self._call_router(
                router_agent,
                candidates,
                message,
                execution_tenant_id=(
                    PLATFORM_TENANT_ID
                    if user_role == UserRoleEnum.PLATFORM_ADMIN.value
                    else tenant_id
                ),
                execution_user_role=user_role,
                execution_user_role_id=user_role_id,
                user_id=user_id,
                has_image_attachments=has_image_attachments,
                has_audio_attachments=has_audio_attachments,
                has_video_attachments=has_video_attachments,
                has_file_attachments=has_file_attachments,
            )
        except Exception as exc:
            logger.error("Router call failed: {}", exc, exc_info=True)
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
                preferred_candidates=preferred_fallback_candidates,
            )

        if not route_result:
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
                preferred_candidates=preferred_fallback_candidates,
            )

        # P4: Validate routed result / 二次校验
        routed_id = route_result.get("agent_id")
        confidence = route_result.get("confidence", 0.0)

        if routed_id not in valid_ids:
            logger.warning(
                "Router selected agent_id={} not in valid_ids, falling back",
                routed_id,
            )
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
                preferred_candidates=preferred_fallback_candidates,
            )

        if confidence < MIN_CONFIDENCE_THRESHOLD:
            logger.info(
                "Router confidence {} below threshold, falling back",
                confidence,
            )
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
                preferred_candidates=preferred_fallback_candidates,
            )

        # Resolve agent name from current candidates / 从当前候选集中解析名称
        agent_name = next((a.name for a in candidates if a.id == routed_id), "")

        return RouteResult(
            agent_id=routed_id,
            agent_name=agent_name,
            confidence=confidence,
            routed_by=ROUTED_BY_ROUTER,
        )

    # ========================================
    # Build candidate list / 构建候选列表
    # ========================================

    async def _list_available_agents(
        self,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None = None,
        user_role_id: int | None = None,
    ) -> list[Agent]:
        return await self.query_service.list_available_agents(
            tenant_id,
            user_role,
            user_id=user_id,
            user_role_id=user_role_id,
        )

    # ========================================
    # Resolve router agent / 查找 Router 智能体
    # ========================================

    async def _get_router_agent(self) -> Agent | None:
        return await self.query_service.get_router_agent()

    # ========================================
    # Call router agent / 调用 Router 智能体
    # ========================================

    async def _call_router(
        self,
        router_agent: Agent,
        candidates: list[Agent],
        message: str,
        *,
        execution_tenant_id: int | None,
        execution_user_role: str,
        execution_user_role_id: int | None = None,
        user_id: int | None = None,
        has_image_attachments: bool = False,
        has_audio_attachments: bool = False,
        has_video_attachments: bool = False,
        has_file_attachments: bool = False,
    ) -> dict[str, Any] | None:
        return await self.runtime_support.call_router_agent(
            router_agent=router_agent,
            candidates=candidates,
            message=message,
            execution_tenant_id=execution_tenant_id or PLATFORM_TENANT_ID,
            execution_user_role=execution_user_role,
            execution_user_role_id=execution_user_role_id,
            user_id=user_id,
            has_image_attachments=has_image_attachments,
            has_audio_attachments=has_audio_attachments,
            has_video_attachments=has_video_attachments,
            has_file_attachments=has_file_attachments,
            agent_can_handle_images_fn=self._agent_can_handle_images,
            billing_context=self._build_router_billing_context(
                router_agent=router_agent,
                tenant_id=execution_tenant_id,
                user_id=user_id,
                user_role=execution_user_role,
            ),
            timeout_seconds=ROUTER_TIMEOUT_SECONDS,
        )

    async def _agent_supports_families(
        self,
        agent: Agent,
        families: list[str],
        *,
        tenant_id: int | None,
    ) -> bool:
        return await agent_supports_executable_families(
            self.db,
            agent,
            families,
            tenant_id=tenant_id,
        )

    # ========================================
    # Fallback handling / 降级逻辑
    # ========================================

    async def _fallback_to_default(
        self,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
        user_role_id: int | None,
        has_image_attachments: bool = False,
        preferred_candidates: list[Agent] | None = None,
    ) -> RouteResult:
        """
        Fallback to the default_chat agent first, then to a preferred
        filtered pool when the default agent cannot satisfy the narrowed
        routing contract.
        优先降级到 default_chat 绑定智能体；若其不满足收窄后的路由约束，再降级到 preferred 候选池。

        Query SystemAgentAssignment with feature_code='default_chat'.
        查询 SystemAgentAssignment，feature_code='default_chat'。
        Tenant-scoped override is checked before the global default.
        企业端优先检查企业覆盖，再回退到全局默认。
        """
        feature_code = "default_chat"
        preferred_candidate_ids = {agent.id for agent in (preferred_candidates or [])}

        assignment: (
            SystemAgentAssignment | None
        ) = await self.query_service.resolve_default_assignment(
            tenant_id=tenant_id,
            user_role=user_role,
            feature_code=feature_code,
        )

        if assignment and assignment.agent_id:
            agent = await self._get_published_agent(assignment.agent_id)
            if agent and await self._is_agent_visible(
                agent,
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
            ):
                if preferred_candidate_ids and agent.id not in preferred_candidate_ids:
                    logger.warning(
                        "Default agent {} is outside preferred fallback pool; using preferred fallback instead",
                        agent.id,
                    )
                else:
                    if has_image_attachments:
                        await self._ensure_agent_supports_images(
                            agent,
                            error_key="agent_chat.error.default_agent_not_vision",
                        )
                    return RouteResult(
                        agent_id=agent.id,
                        agent_name=agent.name,
                        confidence=1.0,
                        routed_by=ROUTED_BY_DEFAULT,
                    )
            elif agent:
                logger.warning(
                    "Default agent {} not visible for tenant={} user_role={}",
                    agent.id,
                    tenant_id,
                    user_role,
                )

        if preferred_candidates:
            return await self._build_preferred_fallback_result(
                preferred_candidates,
                has_image_attachments=has_image_attachments,
            )

        if assignment and assignment.agent_id:
            raise BusinessException(
                message=_("agent_chat.error.default_agent_not_accessible"),
            )

        raise BusinessException(
            message=_("agent_chat.error.default_agent_not_configured"),
        )

    # ========================================
    # Helpers / 辅助方法
    # ========================================

    async def _build_preferred_fallback_result(
        self,
        preferred_candidates: list[Agent],
        *,
        has_image_attachments: bool,
    ) -> RouteResult:
        preferred_agent = preferred_candidates[0]
        if has_image_attachments:
            await self._ensure_agent_supports_images(
                preferred_agent,
                error_key="agent_chat.error.default_agent_not_vision",
            )
        logger.info(
            "Router fallback: using preferred candidate {} ({}) from filtered candidate pool",
            preferred_agent.id,
            preferred_agent.name,
        )
        return RouteResult(
            agent_id=preferred_agent.id,
            agent_name=preferred_agent.name,
            confidence=1.0,
            routed_by=ROUTED_BY_PREFERRED_FALLBACK,
        )

    async def _get_published_agent(self, agent_id: int) -> Agent | None:
        return await self.query_service.get_published_agent(agent_id)

    async def _get_accessible_conversation(
        self,
        conversation_id: int,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
    ) -> Any:
        return await self.query_service.get_accessible_conversation(
            conversation_id,
            tenant_id,
            user_role,
            user_id=user_id,
        )

    async def _is_agent_visible(
        self,
        agent: Agent,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
        user_role_id: int | None,
    ) -> bool:
        return await self.query_service.is_agent_visible(
            agent,
            tenant_id,
            user_role,
            user_id=user_id,
            user_role_id=user_role_id,
        )

    async def _agent_can_handle_images(self, agent: Agent | None) -> bool:
        return await agent_can_handle_images(self.db, agent)

    async def _ensure_agent_supports_images(
        self,
        agent: Agent | None,
        *,
        error_key: str,
    ) -> None:
        if await self._agent_can_handle_images(agent):
            return
        raise BusinessException(message=_(error_key))

    _build_router_billing_context = staticmethod(
        AgentRouterRuntimeSupport.build_router_billing_context,
    )


__all__ = ["AgentRouterService", "RouteResult"]
