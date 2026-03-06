"""
执行引擎类型定义

定义执行请求、执行结果、批量处理等数据类
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.ai.constants import (
    DEFAULT_MEMORY_SCENE,
    MEMORY_CHANNEL_SYSTEM,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage
from app.enums.agent import AgentExecutionModeEnum
from app.enums.common import UserRoleEnum

if TYPE_CHECKING:
    from app.ai.routing.router import RouteResult


@dataclass
class ExecutionRequest:
    """
    执行请求

    Attributes:
        agent_id: 智能体 ID
        tenant_id: 租户 ID
        user_id: 用户 ID（可选，匿名/API 调用时为 None）
        messages: 用户消息列表（conversation 模式）
        input_variables: 输入变量（task/batch 模式，注入到 system_prompt）
        execution_mode: 执行模式（conversation/task/batch/api）
        stream: 是否流式输出
        conversation_id: 对话 ID（conversation 模式续接会话）
    """

    agent_id: int
    tenant_id: int
    user_id: int | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    input_variables: dict[str, Any] = field(default_factory=dict)
    execution_mode: str = AgentExecutionModeEnum.CONVERSATION.value
    stream: bool = False
    conversation_id: int | None = None
    knowledge_base_ids: list[int] | None = None

    # 用户附件（图片/文件，附加到最新用户消息）
    attachments: list[dict[str, Any]] | None = None

    # 会话级授权（前端 sessionStorage 传入，格式: ["read:agents", "create:agents"]）
    consented_actions: list[str] | None = None

    # 用户角色（platform_admin / tenant_admin / tenant_user）
    user_role: str = UserRoleEnum.TENANT_ADMIN.value
    # 用户 RBAC 权限码集合
    permissions: set[str] | None = None

    # API 模式控制标志（由调用方或 dispatcher 自动设置）
    skip_quota: bool = False
    skip_persistence: bool = False
    skip_logging: bool = False

    # 会话记忆场景控制（入口边界）
    # scene：请求来源场景（ai_chat_page/admin_chat/plugin/ai_gateway/unknown）
    # channel：渠道（tenant_chat/admin_chat/plugin/system）
    # source：来源标识（如 ai_chat_page / plugin.weather-widget）
    memory_scene: str = DEFAULT_MEMORY_SCENE
    memory_channel: str = MEMORY_CHANNEL_SYSTEM
    memory_source: str = ""
    memory_enabled: bool = False

    # 前端页面会话 ID（用于 PageOperationExecutor 定位目标页面实例）
    page_session_id: str | None = None


@dataclass
class ExecutionResult:
    """
    执行结果

    Attributes:
        success: 是否成功
        output: 最终输出文本
        messages: 完整消息列表（含 system/user/assistant/tool）
        tool_results: 工具调用结果列表
        total_tokens: 总 Token 消耗
        duration_ms: 总执行耗时（毫秒）
        conversation_id: 对话 ID（conversation 模式）
        error: 错误信息
    """

    success: bool = True
    output: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    total_tokens: int = 0
    duration_ms: int = 0
    conversation_id: int | None = None
    error: str = ""


@dataclass
class PreparedExecution:
    """
    预处理执行上下文

    由 _prepare_execution() 构建，供 execute() 和 stream_execute() 共享。

    Attributes:
        messages: 构建好的消息列表（含 system + 历史 + RAG 注入）
        tools: 优化后的工具定义列表
        rag_sources: RAG 引用来源（无 RAG 时为 None）
        tool_consent_modes: 工具名 → consent_mode 映射
        optimize_event: 工具优化事件数据（SSE 推送用，无优化时为 None）
        route_result: 路由结果（ModelRouter 选出，无路由时为 None）
    """

    messages: list[ChatMessage] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)
    rag_sources: list[dict[str, Any]] | None = None
    tool_consent_modes: dict[str, str] = field(default_factory=dict)
    optimize_event: dict[str, Any] | None = None
    route_result: RouteResult | None = None


@dataclass
class BatchItem:
    """
    批处理单项

    Attributes:
        item_id: 项目唯一标识
        input_variables: 输入变量
        status: 状态 (pending/succeeded/failed)
        result: 执行结果
    """

    item_id: str
    input_variables: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: ExecutionResult | None = None


@dataclass
class BatchResult:
    """
    批处理结果

    Attributes:
        items: 所有项目及其结果
        total: 总数
        succeeded: 成功数
        failed: 失败数
        duration_ms: 总执行耗时（毫秒）
    """

    batch_run_id: int | None = None
    items: list[BatchItem] = field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    duration_ms: int = 0


__all__ = [
    "ExecutionRequest",
    "ExecutionResult",
    "PreparedExecution",
    "BatchItem",
    "BatchResult",
]
