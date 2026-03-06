"""
智能体路由服务

根据用户消息和页面上下文，通过 Router 智能体智能选择最合适的目标智能体。
支持 scope-aware 候选列表过滤和多层安全校验。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import AgentExecutionModeEnum, AgentStatusEnum
from app.enums.common import ResourceScopeEnum
from app.exceptions import BusinessException
from app.models.ai.agent import Agent
from app.models.system.agent_assignment import SystemAgentAssignment
from app.repositories.system.resource_tenant_assignment_repository import (
    assigned_resource_ids_subquery,
)

logger = LogManager.get_logger("ai")

# 需要分配表的 scope 值
_ASSIGNED_SCOPES = (
    ResourceScopeEnum.ASSIGNED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
)

# 路由方式常量
ROUTED_BY_PINNED = "pinned"
ROUTED_BY_ROUTER = "router"
ROUTED_BY_DEFAULT = "default"

# Router 超时秒数
ROUTER_TIMEOUT_SECONDS = 15

# 最低置信度阈值
MIN_CONFIDENCE_THRESHOLD = 0.3


@dataclass
class RouteResult:
    """路由结果"""

    agent_id: int
    agent_name: str
    confidence: float
    routed_by: str


class AgentRouterService:
    """
    智能体路由服务

    流程:
    1. pinned_agent_id 直通（用户手动选择）
    2. 构建 scope-aware 候选列表
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
        is_admin_context: bool = False,
        page_context: dict[str, Any] | None = None,
        pinned_agent_id: int | None = None,
    ) -> RouteResult:
        """
        执行智能路由

        Args:
            tenant_id: 租户 ID（管理端可为 None）
            message: 用户消息
            is_admin_context: 是否管理端上下文
            page_context: 页面上下文信息
            pinned_agent_id: 用户固定选择的智能体 ID

        Returns:
            RouteResult 路由结果
        """
        # P1: pinned 直通
        if pinned_agent_id:
            agent = await self._get_published_agent(pinned_agent_id)
            if agent:
                # 校验 scope 可见性
                if await self._is_agent_visible(
                    agent, tenant_id, is_admin_context
                ):
                    return RouteResult(
                        agent_id=agent.id,
                        agent_name=agent.name,
                        confidence=1.0,
                        routed_by=ROUTED_BY_PINNED,
                    )
                logger.warning(
                    "Pinned agent %s not accessible for tenant=%s admin=%s",
                    pinned_agent_id, tenant_id, is_admin_context,
                )

        # P2: 构建候选列表
        candidates = await self._list_available_agents(
            tenant_id, is_admin_context
        )
        if not candidates:
            return await self._fallback_to_default(
                tenant_id, is_admin_context
            )

        valid_ids = {a.id for a in candidates}

        # P3: 获取 Router 智能体
        router_agent = await self._get_router_agent()
        if not router_agent:
            logger.warning("Router agent not found, falling back to default")
            return await self._fallback_to_default(
                tenant_id, is_admin_context
            )

        if not router_agent.model_id:
            logger.warning("Router agent model not configured")
            return await self._fallback_to_default(
                tenant_id, is_admin_context
            )

        # P3.5: 调用 Router 智能体（TASK 模式）
        try:
            route_result = await self._call_router(
                router_agent, candidates, message, page_context
            )
        except Exception as exc:
            logger.error("Router call failed: %s", exc, exc_info=True)
            return await self._fallback_to_default(
                tenant_id, is_admin_context
            )

        if not route_result:
            return await self._fallback_to_default(
                tenant_id, is_admin_context
            )

        # P4: 二次校验
        routed_id = route_result.get("agent_id")
        confidence = route_result.get("confidence", 0.0)

        if routed_id not in valid_ids:
            logger.warning(
                "Router selected agent_id=%s not in valid_ids, falling back",
                routed_id,
            )
            return await self._fallback_to_default(
                tenant_id, is_admin_context
            )

        if confidence < MIN_CONFIDENCE_THRESHOLD:
            logger.info(
                "Router confidence %.2f below threshold, falling back",
                confidence,
            )
            return await self._fallback_to_default(
                tenant_id, is_admin_context
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
    # 候选列表构建（scope-aware）
    # ========================================

    async def _list_available_agents(
        self,
        tenant_id: int | None,
        is_admin_context: bool,
    ) -> list[Agent]:
        """
        获取 scope-aware 候选智能体列表

        管理端: ADMIN_ONLY / ADMIN_AND_ALL / ADMIN_AND_ASSIGNED
        租户端: ALL_TENANTS / ADMIN_AND_ALL + 同租户 + 已分配
        """
        query = (
            select(Agent)
            .where(
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
                Agent.execution_mode != AgentExecutionModeEnum.ROUTER.value,
            )
        )

        if is_admin_context:
            # 管理端：只看 admin 可见 scope
            query = query.where(
                Agent.scope.in_([
                    ResourceScopeEnum.ADMIN_ONLY.value,
                    ResourceScopeEnum.ADMIN_AND_ALL.value,
                    ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
                    ResourceScopeEnum.ALL_TENANTS.value,
                ])
            )
        elif tenant_id:
            # 租户端：scope-aware 过滤
            assigned_subq = assigned_resource_ids_subquery("agent", tenant_id)
            query = query.where(
                or_(
                    Agent.tenant_id == tenant_id,
                    Agent.scope == ResourceScopeEnum.ADMIN_AND_ALL.value,
                    and_(
                        Agent.scope == ResourceScopeEnum.ALL_TENANTS.value,
                        Agent.tenant_id.is_(None),
                    ),
                    and_(
                        Agent.scope.in_(_ASSIGNED_SCOPES),
                        Agent.id.in_(assigned_subq),
                    ),
                )
            )
        else:
            # 无 tenant_id 也非管理端 → 空
            return []

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ========================================
    # Router 智能体查找
    # ========================================

    async def _get_router_agent(self) -> Agent | None:
        """获取 execution_mode=router 的系统智能体"""
        result = await self.db.execute(
            select(Agent).where(
                Agent.execution_mode == AgentExecutionModeEnum.ROUTER.value,
                Agent.is_system.is_(True),
                Agent.tenant_id.is_(None),
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
    ) -> dict[str, Any] | None:
        """
        TASK 模式调用 Router 智能体，解析 JSON 结果

        Returns:
            {"agent_id": int, "confidence": float} or None
        """
        import asyncio

        from app.ai.engine.dispatcher import ExecutionDispatcher
        from app.ai.engine.types import ExecutionRequest
        from app.ai.types import ChatMessage

        # 构建候选列表描述
        agent_list = []
        for a in candidates:
            agent_list.append({
                "id": a.id,
                "name": a.name,
                "description": a.description or "",
            })

        # 构建路由指令消息
        routing_prompt = (
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
            tenant_id=router_agent.tenant_id or 0,
            messages=[ChatMessage(role="user", content=routing_prompt)],
            execution_mode=AgentExecutionModeEnum.TASK.value,
            stream=False,
        )

        dispatcher = ExecutionDispatcher(self.db)

        try:
            result = await asyncio.wait_for(
                dispatcher.dispatch(request),
                timeout=ROUTER_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("Router agent timed out after %ss", ROUTER_TIMEOUT_SECONDS)
            return None

        if not result.success or not result.output:
            logger.warning("Router agent returned no output: %s", result.error)
            return None

        # 解析 JSON
        return self._parse_router_output(result.output)

    @staticmethod
    def _parse_router_output(output: str) -> dict[str, Any] | None:
        """从 Router 输出中提取 JSON"""
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

        logger.warning("Failed to parse router output: %s", output[:200])
        return None

    # ========================================
    # 降级逻辑
    # ========================================

    async def _fallback_to_default(
        self,
        tenant_id: int | None,
        is_admin_context: bool,
    ) -> RouteResult:
        """
        降级到 default_chat 绑定的智能体

        查询 SystemAgentAssignment: feature_code='default_chat'
        租户端先查租户覆盖，再 fallback 全局默认
        """
        feature_code = "default_chat"

        assignment: SystemAgentAssignment | None = None

        if tenant_id and not is_admin_context:
            # 租户端：先查覆盖
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
        """获取已发布的智能体"""
        result = await self.db.execute(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.status == AgentStatusEnum.PUBLISHED.value,
                Agent.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def _is_agent_visible(
        self,
        agent: Agent,
        tenant_id: int | None,
        is_admin_context: bool,
    ) -> bool:
        """检查智能体对当前上下文是否可见"""
        from app.core.scope import ScopeChecker

        if is_admin_context:
            return ScopeChecker.is_visible_to_admin(agent.scope)

        if not tenant_id:
            return False

        return await ScopeChecker.is_visible_to_tenant(
            scope=agent.scope,
            resource_type="agent",
            resource_id=agent.id,
            tenant_id=tenant_id,
            db=self.db,
        )


__all__ = ["AgentRouterService", "RouteResult"]
