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
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.navigation_semantics import (
    has_navigation_intent,
)
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.routing.router import ModelRouter
from app.ai.text_semantics import (
    collapse_whitespace,
    extract_fenced_json_block,
    extract_first_json_object_with_key,
)
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
from app.models.ai.skill import Skill
from app.models.system.agent_assignment import SystemAgentAssignment
from app.repositories.ai.agent_repository import _tenant_available_condition
from app.services.ai.agent_service import AgentService

logger = LogManager.get_logger("ai")

# Routing method constants / 路由方式常量
ROUTED_BY_PINNED = "pinned"
ROUTED_BY_ROUTER = "router"
ROUTED_BY_DEFAULT = "default"
ROUTED_BY_PREFERRED_FALLBACK = "preferred_fallback"
ROUTED_BY_CONVERSATION = "conversation"

# Router timeout in seconds / Router 超时秒数
ROUTER_TIMEOUT_SECONDS = 15

# Minimum confidence threshold / 最低置信度阈值
MIN_CONFIDENCE_THRESHOLD = 0.3

PAGE_OPERATION_REQUIRED_SKILLS = frozenset(
    {"get_page_context", "invoke_page_operation"},
)
PAGE_OPERATION_STRONG_INTENT_TOKENS = (
    "operate on the current page",
    "operate on this page",
    "perform the page action",
    "help me operate on the current page",
    "帮我操作当前页面",
    "帮我操作这个页面",
    "操作当前页面",
    "操作这个页面",
    "操作本页面",
)
PAGE_OPERATION_REFERENCE_TOKENS = (
    "current page",
    "current form",
    "current screen",
    "this page",
    "this form",
    "当前页面",
    "当前表单",
    "这个页面",
    "本页面",
    "当前界面",
    "这个表单",
)
PAGE_OPERATION_ACTION_TOKENS = (
    "apply",
    "add",
    "change",
    "click",
    "configure",
    "create",
    "delete",
    "edit",
    "fill",
    "filter",
    "open",
    "refresh",
    "save",
    "search",
    "select",
    "set",
    "switch to",
    "submit",
    "switch",
    "update",
    "visit",
    "go to",
    "jump to",
    "navigate",
    "进入",
    "添加",
    "保存",
    "修改",
    "切换",
    "切到",
    "创建",
    "删除",
    "刷新",
    "新增",
    "填写",
    "打开",
    "操作",
    "搜索",
    "提交",
    "跳转",
    "新建",
    "点击",
    "筛选",
    "编辑",
    "设置",
    "配置",
)
PAGE_OPERATION_TARGET_TOKENS = (
    "button",
    "dialog",
    "drawer",
    "form",
    "list",
    "menu",
    "modal",
    "tab",
    "按钮",
    "列表",
    "菜单",
    "表单",
    "页签",
    "弹窗",
    "抽屉",
    "对话框",
)


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

        page_operation_routing_required = self._requires_page_operation_routing(
            message,
            page_context,
        )
        page_operation_filtered = False

        if has_image_attachments:
            vision_candidates = [
                a for a in candidates if await self._agent_can_handle_images(a)
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

        if page_operation_routing_required:
            page_operation_candidates = [
                agent
                for agent in candidates
                if self._agent_supports_page_operations(agent)
            ]
            if page_operation_candidates:
                candidates = page_operation_candidates
                page_operation_filtered = True
                logger.info(
                    "Agent router: narrowed to {} page-operation-capable agents",
                    len(candidates),
                )
            else:
                logger.warning(
                    "Agent router: page operation intent detected but no page-operation-capable agent was found; using general candidate pool",
                )

        if page_operation_filtered and len(candidates) == 1:
            agent = candidates[0]
            logger.info(
                "Agent router: directly selected page-operation-capable agent {} ({})",
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
        preferred_fallback_candidates = candidates if page_operation_filtered else None

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
        """
        获取当前上下文可用的候选智能体列表。
        Get candidate agents available under the current context.
        """
        query = (
            select(Agent)
            .options(
                selectinload(Agent.model),
                selectinload(Agent.skill_grants)
                .selectinload(AgentSkillGrant.skill)
                .selectinload(Skill.package),
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
            return sorted(agents, key=lambda item: item.id)
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
        return sorted(visible, key=lambda item: item.id)

    # ========================================
    # Resolve router agent / 查找 Router 智能体
    # ========================================

    async def _get_router_agent(self) -> Agent | None:
        """获取 execution_mode=router 的系统智能体 / Get system agent with execution_mode=router."""
        result = await self.db.execute(
            select(Agent)
            .where(
                Agent.execution_mode == AgentExecutionModeEnum.ROUTER.value,
                Agent.is_system.is_(True),
                Agent.owner_tenant_id.is_(None),
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
            )
            .order_by(Agent.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ========================================
    # Call router agent / 调用 Router 智能体
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
        has_audio_attachments: bool = False,
        has_video_attachments: bool = False,
        has_file_attachments: bool = False,
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

        # Build candidate descriptions (capability hints for Router) / 构建候选描述（能力摘要，供 Router 选 Agent）
        agent_list = []
        for a in candidates:
            entry: dict[str, Any] = {
                "id": a.id,
                "name": a.name,
                "description": a.description or "",
            }
            entry["supports_vision"] = await self._agent_can_handle_images(a)
            # Collect enabled skill names (tool surface for Router) / 提取已启用技能名，告知工具能力
            skill_grants = getattr(a, "skill_grants", None)
            if skill_grants:
                skill_names = []
                for grant in skill_grants:
                    skill_name = self._grant_skill_name_if_active(grant)
                    if skill_name:
                        skill_names.append(skill_name)
                if skill_names:
                    entry["capabilities"] = skill_names
            agent_list.append(entry)

        # 构建路由指令消息 / Build routing instruction message
        vision_preamble = ""
        if has_image_attachments:
            vision_preamble = render_prompt_contract("agent_router_vision_preamble")
        attachment_notes: list[str] = []
        if has_audio_attachments:
            attachment_notes.append("audio")
        if has_video_attachments:
            attachment_notes.append("video")
        if has_file_attachments:
            attachment_notes.append("file")

        attachment_preamble = ""
        if attachment_notes:
            attachment_preamble = render_prompt_contract(
                "agent_router_attachment_preamble",
                attachment_types=", ".join(attachment_notes),
            )

        routing_prompt = render_prompt_contract(
            "agent_router_selection",
            vision_preamble=vision_preamble.strip(),
            attachment_preamble=attachment_preamble.strip(),
            agent_list_json=json.dumps(agent_list, ensure_ascii=False),
            page_context_json=(
                json.dumps(page_context, ensure_ascii=False) if page_context else ""
            ),
            message=message,
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

        # Parse JSON from router output / 解析 Router 输出的 JSON
        return self._parse_router_output(result.output)

    @staticmethod
    def _parse_router_output(output: str) -> dict[str, Any] | None:
        """从 Router 输出中提取 JSON / Extract JSON from Router output."""
        # 尝试直接解析 / Try direct parse first
        try:
            data = json.loads(output.strip())
            if isinstance(data, dict) and "agent_id" in data:
                return {
                    "agent_id": int(data["agent_id"]),
                    "confidence": float(data.get("confidence", 0.5)),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # Extract JSON from fenced code block / 从 ``` 代码块提取 JSON
        json_block = extract_fenced_json_block(output)
        if json_block:
            try:
                data = json.loads(json_block)
                if isinstance(data, dict) and "agent_id" in data:
                    return {
                        "agent_id": int(data["agent_id"]),
                        "confidence": float(data.get("confidence", 0.5)),
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        # Match bare JSON object with agent_id / 匹配含 agent_id 的裸 JSON
        data = extract_first_json_object_with_key(output, "agent_id")
        if data is not None:
            try:
                return {
                    "agent_id": int(data["agent_id"]),
                    "confidence": float(data.get("confidence", 0.5)),
                }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

        logger.warning("Failed to parse router output: {}", output[:200])
        return None

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

        assignment: SystemAgentAssignment | None = None

        if tenant_id and user_role != UserRoleEnum.PLATFORM_ADMIN.value:
            # Tenant override first / 企业端优先查询覆盖配置
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
            # Global default fallback / 全局默认兜底
            result = await self.db.execute(
                select(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code == feature_code,
                    SystemAgentAssignment.tenant_id.is_(None),
                    SystemAgentAssignment.is_active.is_(True),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            assignment = result.scalar_one_or_none()

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
        """获取已发布的智能体 / Get published agent."""
        result = await self.db.execute(
            select(Agent)
            .options(
                selectinload(Agent.model),
                selectinload(Agent.skill_grants)
                .selectinload(AgentSkillGrant.skill)
                .selectinload(Skill.package),
            )
            .where(
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
                AgentConversation.owner_type
                == ConversationOwnerTypeEnum.PLATFORM_ADMIN.value,
            )
        elif tenant_id:
            stmt = stmt.where(
                AgentConversation.tenant_id == tenant_id,
                AgentConversation.owner_type
                == ConversationOwnerTypeEnum.from_user_role(
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

    @staticmethod
    def _agent_skill_names(agent: Agent | None) -> set[str]:
        if agent is None:
            return set()

        skill_names: set[str] = set()
        skill_grants = getattr(agent, "skill_grants", None) or []
        for grant in skill_grants:
            skill_name = AgentRouterService._grant_skill_name_if_active(grant)
            if skill_name:
                skill_names.add(skill_name)
        return skill_names

    @staticmethod
    def _grant_skill_name_if_active(grant: AgentSkillGrant | Any) -> str | None:
        if getattr(grant, "enabled", True) is False:
            return None
        skill = getattr(grant, "skill", None)
        if not skill:
            return None
        if not getattr(skill, "is_active", True) or getattr(skill, "is_deleted", False):
            return None
        package = getattr(skill, "package", None)
        if package is None:
            return None
        if not getattr(package, "is_active", True) or getattr(
            package, "is_deleted", False
        ):
            return None
        skill_name = getattr(skill, "name", None)
        if isinstance(skill_name, str) and skill_name:
            return skill_name
        return None

    @classmethod
    def _agent_supports_page_operations(cls, agent: Agent | None) -> bool:
        return PAGE_OPERATION_REQUIRED_SKILLS.issubset(
            cls._agent_skill_names(agent),
        )

    @staticmethod
    def _page_context_has_available_operations(
        page_context: dict[str, Any] | None,
    ) -> bool:
        if not isinstance(page_context, dict):
            return False

        page_data = page_context.get("page_data")
        if isinstance(page_data, dict):
            operations = page_data.get("available_operations")
            if isinstance(operations, list) and len(operations) > 0:
                return True

        operations = page_context.get("available_operations")
        return isinstance(operations, list) and len(operations) > 0

    @staticmethod
    def _page_context_supports_navigation(
        page_context: dict[str, Any] | None,
    ) -> bool:
        if not isinstance(page_context, dict):
            return False

        raw_operations: list[Any] = []
        page_data = page_context.get("page_data")
        if isinstance(page_data, dict) and isinstance(
            page_data.get("available_operations"), list
        ):
            raw_operations = page_data.get("available_operations") or []
        elif isinstance(page_context.get("available_operations"), list):
            raw_operations = page_context.get("available_operations") or []

        operation_names = {
            str(item.get("name") or "").strip()
            for item in raw_operations
            if isinstance(item, dict)
        }
        return (
            "navigate_menu" in operation_names
            or "list_available_menus" in operation_names
        )

    @classmethod
    def _requires_page_operation_routing(
        cls,
        message: str,
        page_context: dict[str, Any] | None,
    ) -> bool:
        if not message or not page_context:
            return False

        normalized_message = collapse_whitespace(message).strip().lower()
        if not normalized_message:
            return False

        if not cls._page_context_has_available_operations(page_context):
            return False

        has_strong_intent = any(
            token in normalized_message for token in PAGE_OPERATION_STRONG_INTENT_TOKENS
        )
        if has_strong_intent:
            return True

        has_action_token = any(
            token in normalized_message for token in PAGE_OPERATION_ACTION_TOKENS
        )
        has_navigation_request = has_navigation_intent(
            normalized_message,
            page_context,
        )
        if has_navigation_request:
            return True

        if (
            cls._page_context_supports_navigation(page_context)
            and has_navigation_request
        ):
            return True

        if not has_action_token:
            return False

        has_reference_token = any(
            token in normalized_message for token in PAGE_OPERATION_REFERENCE_TOKENS
        )
        if has_reference_token:
            return True

        return any(
            token in normalized_message for token in PAGE_OPERATION_TARGET_TOKENS
        )

    async def _agent_can_handle_images(self, agent: Agent | None) -> bool:
        if agent is None:
            return False
        if self._agent_supports_images(agent):
            return True
        needs_fc = self._agent_needs_function_calling(agent)
        return await ModelRouter(self.db).can_handle_attachments(
            agent,
            has_image=True,
            needs_fc=needs_fc,
        )

    async def _ensure_agent_supports_images(
        self,
        agent: Agent | None,
        *,
        error_key: str,
    ) -> None:
        if await self._agent_can_handle_images(agent):
            return
        raise BusinessException(message=_(error_key))

    @staticmethod
    def _agent_needs_function_calling(agent: Agent | None) -> bool:
        skill_grants = getattr(agent, "skill_grants", None) or []
        for grant in skill_grants:
            if AgentRouterService._grant_skill_name_if_active(grant):
                return True
        return False

    @staticmethod
    def _build_router_billing_context(
        *,
        router_agent: Agent,
        tenant_id: int | None,
        user_id: int | None,
        user_role: str,
    ) -> dict[str, Any]:
        billing_tenant_id = (
            tenant_id
            if tenant_id is not None and tenant_id > PLATFORM_TENANT_ID
            else None
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
