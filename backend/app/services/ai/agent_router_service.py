"""
智能体路由服务 / Agent Router Service

根据用户消息和页面上下文，通过 Router 智能体智能选择最合适的目标智能体。
Selects the most suitable target agent via Router agent based on user messages and page context.
候选过滤遵循平台分发、企业发布和端内访问控制的新语义。
Candidate filtering follows the new platform distribution, tenant publication,
and endpoint-internal access semantics.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import PLATFORM_TENANT_ID
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
    ConversationOwnerTypeEnum,
)
from app.enums.ai import CallAccessChannelEnum
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.models.ai.agent_conversation import AgentConversation
from app.models.ai.agent_skill_grant import AgentSkillGrant
from app.models.system.agent_assignment import SystemAgentAssignment
from app.repositories.ai.agent_repository import _tenant_available_condition
from app.services.ai.agent_service import AgentService

logger = LogManager.get_logger("ai")

# 路由方式常量
ROUTED_BY_PINNED = "pinned"
ROUTED_BY_ROUTER = "router"
ROUTED_BY_DEFAULT = "default"
ROUTED_BY_CONVERSATION = "conversation"

# Router 超时秒数
ROUTER_TIMEOUT_SECONDS = 15

# 最低置信度阈值
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

    async def route(
        self,
        tenant_id: int | None,
        message: str,
        conversation_id: int | None = None,
        page_context: dict[str, Any] | None = None,
        pinned_agent_id: int | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        user_id: int | None = None,
        force_reroute: bool = False,
        has_image_attachments: bool = False,
    ) -> RouteResult:
        """
        执行智能路由 / Execute agent routing.

        Args：
            tenant_id: 企业 ID（管理端可为 None）
            message: 用户消息
            conversation_id: 已有对话 ID（若存在且未 force_reroute，则沿用当前对话绑定智能体）
            page_context: 页面上下文信息
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
                    self._ensure_agent_supports_images(
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

        # P1: pinned 直通
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
                        self._ensure_agent_supports_images(
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
                    pinned_agent_id, tenant_id, user_role,
                )

        # P2: 构建候选列表
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

        if has_image_attachments:
            vision_candidates = [
                a for a in candidates
                if getattr(getattr(a, "model", None), "supports_vision", False)
            ]
            if not vision_candidates:
                raise BusinessException(
                    message=_("agent_chat.error.no_vision_agent_available"),
                )
            candidates = vision_candidates
            logger.info(
                "Agent router: narrowed to {} vision-capable agents (image attachments)",
                len(candidates),
            )

        valid_ids = {a.id for a in candidates}

        # P3: 获取 Router 智能体
        router_agent = await self._get_router_agent()
        if not router_agent:
            logger.warning("Router agent not found, falling back to default")
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
            )

        if not router_agent.model_id:
            logger.warning("Router agent model not configured")
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
            )

        # P3.5: 调用 Router 智能体（TASK 模式）
        try:
            route_result = await self._call_router(
                router_agent,
                candidates,
                message,
                page_context,
                execution_tenant_id=(
                    PLATFORM_TENANT_ID
                    if user_role == UserRoleEnum.PLATFORM_ADMIN.value
                    else tenant_id
                ),
                execution_user_role=user_role,
                execution_user_role_id=user_role_id,
                user_id=user_id,
                has_image_attachments=has_image_attachments,
            )
        except Exception as exc:
            logger.error("Router call failed: {}", exc, exc_info=True)
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
            )

        if not route_result:
            return await self._fallback_to_default(
                tenant_id,
                user_role,
                user_id=user_id,
                user_role_id=user_role_id,
                has_image_attachments=has_image_attachments,
            )

        # P4: 二次校验
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
            )

        # 查找候选中的名称
        agent_name = next(
            (a.name for a in candidates if a.id == routed_id), ""
        )

        return RouteResult(
            agent_id=routed_id,
            agent_name=agent_name,
            confidence=confidence,
            routed_by=ROUTED_BY_ROUTER,
        )

    # ========================================
    # 候选列表构建
    # ========================================

    async def _list_available_agents(
        self,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None = None,
        user_role_id: int | None = None,
    ) -> list[Agent]:
        """
        获取当前上下文可用的候选智能体列表。
        Get candidate agents available under the current context.
        """
        query = (
            select(Agent)
            .options(
                selectinload(Agent.model),
                selectinload(Agent.skill_grants).selectinload(AgentSkillGrant.skill),
            )
            .where(
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
                Agent.execution_mode != AgentExecutionModeEnum.ROUTER.value,
            )
        )

        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            query = query.where(Agent.owner_tenant_id.is_(None))
            agents = list((await self.db.execute(query)).scalars().unique().all())
            return agents
        elif tenant_id:
            query = query.where(_tenant_available_condition(tenant_id))
        else:
            return []

        agents = list((await self.db.execute(query)).scalars().all())
        if not agents:
            return []

        agent_service = AgentService(self.db, tenant_id)
        visible: list[Agent] = []
        for agent in agents:
            allowed = await agent_service.check_user_access(
                agent_id=agent.id,
                user_id=user_id or 0,
                user_role=user_role,
                user_role_id=user_role_id,
            )
            if allowed:
                visible.append(agent)
        return visible

    # ========================================
    # Router 智能体查找
    # ========================================

    async def _get_router_agent(self) -> Agent | None:
        """获取 execution_mode=router 的系统智能体 / Get system agent with execution_mode=router."""
        result = await self.db.execute(
            select(Agent).where(
                Agent.execution_mode == AgentExecutionModeEnum.ROUTER.value,
                Agent.is_system.is_(True),
                Agent.owner_tenant_id.is_(None),
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
            ).order_by(Agent.id.asc()).limit(1)
        )
        return result.scalar_one_or_none()

    # ========================================
    # 调用 Router 智能体
    # ========================================

    async def _call_router(
        self,
        router_agent: Agent,
        candidates: list[Agent],
        message: str,
        page_context: dict[str, Any] | None,
        *,
        execution_tenant_id: int | None,
        execution_user_role: str,
        execution_user_role_id: int | None = None,
        user_id: int | None = None,
        has_image_attachments: bool = False,
    ) -> dict[str, Any] | None:
        """
        TASK 模式调用 Router 智能体，解析 JSON 结果 / TASK mode: call Router agent and parse JSON result.

        Returns:
            {"agent_id": int, "confidence": float} or None
        """
        import asyncio

        from app.ai.engine.dispatcher import ExecutionDispatcher
        from app.ai.engine.types import ExecutionRequest
        from app.ai.types import ChatMessage

        # 构建候选列表描述（含能力摘要，帮助 Router 选择合适的 Agent）
        agent_list = []
        for a in candidates:
            m = getattr(a, "model", None)
            entry: dict[str, Any] = {
                "id": a.id,
                "name": a.name,
                "description": a.description or "",
            }
            if m is not None:
                entry["supports_vision"] = bool(getattr(m, "supports_vision", False))
            # 提取已启用技能名称列表，让 Router 知道 Agent 的工具能力
            skill_grants = getattr(a, "skill_grants", None)
            if skill_grants:
                skill_names = []
                for grant in skill_grants:
                    if not getattr(grant, "enabled", True):
                        continue
                    skill = getattr(grant, "skill", None)
                    if skill and getattr(skill, "name", None):
                        skill_names.append(skill.name)
                if skill_names:
                    entry["capabilities"] = skill_names
            agent_list.append(entry)

        # 构建路由指令消息
        vision_preamble = ""
        if has_image_attachments:
            vision_preamble = (
                "IMPORTANT: The user message includes image attachment(s). "
                "You MUST select an agent with supports_vision=true (listed in JSON). "
                "Do not choose an agent that cannot analyze images.\n\n"
            )
        routing_prompt = vision_preamble + (
            "Based on the user's message and context, select the most appropriate agent.\n\n"
            f"Available agents:\n{json.dumps(agent_list, ensure_ascii=False)}\n\n"
        )
        if page_context:
            routing_prompt += f"Page context:\n{json.dumps(page_context, ensure_ascii=False)}\n\n"

        routing_prompt += (
            f"User message: {message}\n\n"
            "Respond with ONLY a JSON object: "
            '{"agent_id": <id>, "confidence": <0.0-1.0>}'
        )

        request = ExecutionRequest(
            agent_id=router_agent.id,
            tenant_id=execution_tenant_id or PLATFORM_TENANT_ID,
            user_id=user_id,
            messages=[ChatMessage(role="user", content=routing_prompt)],
            execution_mode=AgentExecutionModeEnum.TASK.value,
            stream=False,
            user_role=execution_user_role,
            user_role_id=execution_user_role_id,
            billing_context=self._build_router_billing_context(
                router_agent=router_agent,
                tenant_id=execution_tenant_id,
                user_id=user_id,
                user_role=execution_user_role,
            ),
        )

        dispatcher = ExecutionDispatcher(self.db)

        try:
            result = await asyncio.wait_for(
                dispatcher.dispatch(request),
                timeout=ROUTER_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("Router agent timed out after {}s", ROUTER_TIMEOUT_SECONDS)
            return None

        if not result.success or not result.output:
            logger.warning("Router agent returned no output: {}", result.error)
            return None

        # 解析 JSON
        return self._parse_router_output(result.output)

    @staticmethod
    def _parse_router_output(output: str) -> dict[str, Any] | None:
        """从 Router 输出中提取 JSON / Extract JSON from Router output."""
        # 尝试直接解析
        try:
            data = json.loads(output.strip())
            if isinstance(data, dict) and "agent_id" in data:
                return {
                    "agent_id": int(data["agent_id"]),
                    "confidence": float(data.get("confidence", 0.5)),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # 尝试提取 JSON 代码块
        json_match = re.search(r'```(?:json)?\s*(\{[^`]+\})\s*```', output, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict) and "agent_id" in data:
                    return {
                        "agent_id": int(data["agent_id"]),
                        "confidence": float(data.get("confidence", 0.5)),
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # 尝试提取裸 JSON 对象
        json_match = re.search(r'\{[^{}]*"agent_id"\s*:\s*\d+[^{}]*\}', output)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                return {
                    "agent_id": int(data["agent_id"]),
                    "confidence": float(data.get("confidence", 0.5)),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        logger.warning("Failed to parse router output: {}", output[:200])
        return None

    # ========================================
    # 降级逻辑
    # ========================================

    async def _fallback_to_default(
        self,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
        user_role_id: int | None,
        has_image_attachments: bool = False,
    ) -> RouteResult:
        """
        降级到 default_chat 绑定的智能体 / Fallback to default_chat bound agent.

        查询 SystemAgentAssignment: feature_code='default_chat'
        企业端先查企业覆盖，再 fallback 全局默认
        """
        feature_code = "default_chat"

        assignment: SystemAgentAssignment | None = None

        if tenant_id and user_role != UserRoleEnum.PLATFORM_ADMIN.value:
            # 企业端：先查覆盖
            result = await self.db.execute(
                select(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code == feature_code,
                    SystemAgentAssignment.tenant_id == tenant_id,
                    SystemAgentAssignment.is_active.is_(True),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            assignment = result.scalar_one_or_none()

        if not assignment:
            # 全局默认
            result = await self.db.execute(
                select(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code == feature_code,
                    SystemAgentAssignment.tenant_id.is_(None),
                    SystemAgentAssignment.is_active.is_(True),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            assignment = result.scalar_one_or_none()

        if not assignment or not assignment.agent_id:
            raise BusinessException(
                message=_("agent_chat.error.default_agent_not_configured"),
            )

        agent = await self._get_published_agent(assignment.agent_id)
        if not agent:
            raise BusinessException(
                message=_("agent_chat.error.default_agent_not_configured"),
            )

        if not await self._is_agent_visible(
            agent,
            tenant_id,
            user_role,
            user_id=user_id,
            user_role_id=user_role_id,
        ):
            logger.warning(
                "Default agent {} not visible for tenant={} user_role={}",
                agent.id, tenant_id, user_role,
            )
            raise BusinessException(
                message=_("agent_chat.error.default_agent_not_accessible"),
            )

        if has_image_attachments:
            self._ensure_agent_supports_images(
                agent,
                error_key="agent_chat.error.default_agent_not_vision",
            )

        return RouteResult(
            agent_id=agent.id,
            agent_name=agent.name,
            confidence=1.0,
            routed_by=ROUTED_BY_DEFAULT,
        )

    # ========================================
    # 辅助方法
    # ========================================

    async def _get_published_agent(self, agent_id: int) -> Agent | None:
        """获取已发布的智能体 / Get published agent."""
        result = await self.db.execute(
            select(Agent).options(selectinload(Agent.model)).where(
                Agent.id == agent_id,
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _get_accessible_conversation(
        self,
        conversation_id: int,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
    ) -> AgentConversation:
        """Resolve an accessible conversation for routing / 为路由解析当前可访问的对话。"""
        stmt = select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.is_deleted.is_(False),
        )
        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            stmt = stmt.where(
                AgentConversation.tenant_id == PLATFORM_TENANT_ID,
                AgentConversation.owner_type == ConversationOwnerTypeEnum.PLATFORM_ADMIN.value,
            )
        elif tenant_id:
            stmt = stmt.where(
                AgentConversation.tenant_id == tenant_id,
                AgentConversation.owner_type == ConversationOwnerTypeEnum.from_user_role(
                    user_role,
                ),
            )
        else:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )

        if user_role != UserRoleEnum.PLATFORM_ADMIN.value and user_id is not None:
            stmt = stmt.where(AgentConversation.user_id == user_id)

        result = await self.db.execute(stmt.limit(1))
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise NotFoundException(
                message=_("agent_chat.error.conversation_not_found"),
            )
        return conversation

    async def _is_agent_visible(
        self,
        agent: Agent,
        tenant_id: int | None,
        user_role: str,
        *,
        user_id: int | None,
        user_role_id: int | None,
    ) -> bool:
        """检查智能体对当前上下文是否可见 / Check agent visible to current context."""
        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            return getattr(agent, "owner_tenant_id", None) is None

        if not tenant_id:
            return False

        try:
            return await AgentService(self.db, tenant_id).check_user_access(
                agent_id=agent.id,
                user_id=user_id or 0,
                user_role=user_role,
                user_role_id=user_role_id,
            )
        except NotFoundException:
            return False

    @staticmethod
    def _agent_supports_images(agent: Agent | None) -> bool:
        model = getattr(agent, "model", None)
        return bool(getattr(model, "supports_vision", False))

    def _ensure_agent_supports_images(
        self,
        agent: Agent | None,
        *,
        error_key: str,
    ) -> None:
        if self._agent_supports_images(agent):
            return
        raise BusinessException(message=_(error_key))

    @staticmethod
    def _build_router_billing_context(
        *,
        router_agent: Agent,
        tenant_id: int | None,
        user_id: int | None,
        user_role: str,
    ) -> dict[str, Any]:
        billing_tenant_id = (
            tenant_id if tenant_id is not None and tenant_id > PLATFORM_TENANT_ID else None
        )
        if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
            access_channel = CallAccessChannelEnum.ADMIN_INTERNAL.value
        elif user_role == UserRoleEnum.TENANT_USER.value:
            access_channel = CallAccessChannelEnum.TENANT_USER.value
        else:
            access_channel = CallAccessChannelEnum.TENANT_ADMIN.value

        _otid = getattr(router_agent, "owner_tenant_id", None)
        return {
            "billing_tenant_id": billing_tenant_id,
            "actor_user_id": user_id,
            "actor_user_type": user_role,
            "access_channel": access_channel,
            "agent_owner_type": ("platform" if _otid is None else "tenant"),
            "agent_owner_tenant_id": _otid,
            "agent_resource_scope": getattr(router_agent, "scope", None),
            "tenant_publication_id": None,
            "publication_enabled_snapshot": None,
            "publication_access_type_snapshot": None,
        }


__all__ = ["AgentRouterService", "RouteResult"]
