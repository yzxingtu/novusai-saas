"""
Execution Engine Type Definitions / 执行引擎类型定义

Defines execution request, execution result, batch processing and other dataclasses.
定义执行请求、执行结果、批量处理等数据类。
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
class ToolUsePolicy:
    """
    Tool-use policy for the current turn / 当前轮次的工具使用策略。

    family:
        Logical tool family currently in focus.
        当前聚焦的工具族。
    mode:
        auto = model may decide; required = tool use is enforced.
        auto = 模型自行判断；required = 强制走工具。
    allowed_tool_names:
        Optional tool-name subset exposed to the model when policy is strict.
        严格模式下暴露给模型的工具名子集。
    retry_on_contract_breach:
        Whether one corrective retry is allowed after a capability denial / no-tool breach.
        发生“能力否认 / 未用工具”违约后是否允许一次纠偏重试。
    reason:
        Human-readable internal reason for diagnostics.
        供诊断使用的内部原因说明。
    """

    family: str = "none"
    mode: str = "auto"
    allowed_tool_names: list[str] = field(default_factory=list)
    retry_on_contract_breach: bool = False
    reason: str = ""


@dataclass
class ExecutionRequest:
    """
    Execution Request / 执行请求

    Attributes:
        agent_id: Agent ID / 智能体 ID
        tenant_id: Tenant ID / 企业 ID
        user_id: User ID (optional, None for anonymous/API calls) / 用户 ID（可选，匿名/API 调用时为 None）
        messages: User message list (conversation mode) / 用户消息列表（conversation 模式）
        input_variables: Input variables (task/batch mode, injected into system_prompt) / 输入变量（task/batch 模式，注入到 system_prompt）
        execution_mode: Execution mode (conversation/task/batch/api) / 执行模式
        stream: Whether to stream output / 是否流式输出
        conversation_id: Conversation ID (for resuming conversation mode) / 对话 ID（conversation 模式续接会话）
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

    # User attachments (images/files, appended to latest user message) / 用户附件（图片/文件，附加到最新用户消息）
    attachments: list[dict[str, Any]] | None = None

    # Session-level authorization (from frontend sessionStorage, format: ["read:agents", "create:agents"]) / 会话级授权（前端 sessionStorage 传入）
    consented_actions: list[str] | None = None

    # User role (platform_admin / tenant_admin / tenant_user) / 用户角色
    user_role: str = UserRoleEnum.TENANT_ADMIN.value
    user_role_id: int | None = None
    # User RBAC permission code set / 用户 RBAC 权限码集合
    permissions: set[str] | None = None

    # Immutable billing / attribution snapshot captured at call time
    # 调用时捕获的不可变计费归属快照
    billing_context: dict[str, Any] | None = None

    # API mode control flags (set by caller or dispatcher automatically) / API 模式控制标志（由调用方或 dispatcher 自动设置）
    skip_quota: bool = False
    skip_persistence: bool = False
    skip_logging: bool = False

    # Session memory scene control (entry boundary) / 会话记忆场景控制（入口边界）
    # scene: request source scene (ai_chat_page/admin_chat/plugin/ai_gateway/unknown)
    # channel: channel (tenant_chat/admin_chat/plugin/system)
    # source: source identifier (e.g. ai_chat_page / plugin.weather-widget)
    memory_scene: str = DEFAULT_MEMORY_SCENE
    memory_channel: str = MEMORY_CHANNEL_SYSTEM
    memory_source: str = ""
    memory_enabled: bool = False

    # Frontend page session ID (for PageOperationExecutor to locate target page instance) / 前端页面会话 ID
    page_session_id: str | None = None
    knowledge_base_feedback: dict[str, Any] | None = None
    tool_use_policy: ToolUsePolicy = field(default_factory=ToolUsePolicy)


@dataclass
class ExecutionResult:
    """
    Execution Result / 执行结果

    Attributes:
        success: Whether successful / 是否成功
        output: Final output text / 最终输出文本
        messages: Complete message list (system/user/assistant/tool) / 完整消息列表
        tool_results: Tool call result list / 工具调用结果列表
        total_tokens: Total token consumption / 总 Token 消耗
        duration_ms: Total execution time (ms) / 总执行耗时（毫秒）
        conversation_id: Conversation ID (conversation mode) / 对话 ID
        error: Error message / 错误信息
        partial: Whether result is partial (interrupted before normal completion) / 是否为 partial（中断导致未正常完成）
        interrupted: Whether execution was interrupted (cancel/disconnect) / 是否被中断（取消/断开）
        completion_reason: Why execution ended (stop/cancel/interrupted/error) / 结束原因
    """

    success: bool = True
    output: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    total_tokens: int = 0
    duration_ms: int = 0
    conversation_id: int | None = None
    runtime_model_id: int | None = None
    runtime_model_name: str | None = None
    runtime_provider_id: int | None = None
    runtime_provider_name: str | None = None
    error: str = ""
    partial: bool = False
    interrupted: bool = False
    completion_reason: str = ""
    rag_sources: list[dict[str, Any]] | None = None


@dataclass
class PreparedExecution:
    """
    Prepared Execution Context / 预处理执行上下文

    Built by _prepare_execution(), shared by execute() and stream_execute().
    由 _prepare_execution() 构建，供 execute() 和 stream_execute() 共享。

    Attributes:
        messages: Built message list (system + history + RAG injection) / 构建好的消息列表
        tools: Optimized tool definition list / 优化后的工具定义列表
        rag_sources: RAG citation sources (None if no RAG) / RAG 引用来源
        tool_consent_modes: Tool name → consent_mode mapping / 工具名 → consent_mode 映射
        optimize_event: Tool optimization event data (for SSE push, None if no optimization) / 工具优化事件数据
        route_result: Route result (from ModelRouter, None if no routing) / 路由结果
    """

    messages: list[ChatMessage] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)
    all_tools: list[ToolDefinition] = field(default_factory=list)
    continuation_context: ResearchContinuationContext | None = None
    tool_use_policy: ToolUsePolicy = field(default_factory=ToolUsePolicy)
    rag_sources: list[dict[str, Any]] | None = None
    tool_consent_modes: dict[str, str] = field(default_factory=dict)
    optimize_event: dict[str, Any] | None = None
    route_result: RouteResult | None = None
    stream_runtime: Any | None = None


@dataclass
class ResearchContinuationContext:
    """Runtime metadata for external web research. / 外部联网研究运行时上下文。"""

    active: bool = False
    family: str | None = None
    origin: str = "none"
    current_user_text: str = ""
    research_target_text: str = ""
    recent_successful_tool_names: list[str] = field(default_factory=list)
    recent_web_queries: list[str] = field(default_factory=list)
    search_query_count: int = 0
    fetched_url_count: int = 0
    research_instruction_texts: list[str] = field(default_factory=list)


@dataclass
class BatchItem:
    """
    Batch Item / 批处理单项

    Attributes:
        item_id: Item unique identifier / 项目唯一标识
        input_variables: Input variables / 输入变量
        status: Status (pending/succeeded/failed) / 状态
        result: Execution result / 执行结果
    """

    item_id: str
    input_variables: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: ExecutionResult | None = None


@dataclass
class BatchResult:
    """
    Batch Result / 批处理结果

    Attributes:
        items: All items and their results / 所有项目及其结果
        total: Total count / 总数
        succeeded: Success count / 成功数
        failed: Failure count / 失败数
        duration_ms: Total execution time (ms) / 总执行耗时（毫秒）
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
    "ResearchContinuationContext",
    "ToolUsePolicy",
    "BatchItem",
    "BatchResult",
]
