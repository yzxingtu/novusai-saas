"""
Hook System / 钩子系统

Provides before/after hook mechanism for execution pipelines.
Hooks differ from events: hooks can modify execution context (intercept/modify data), events are notification-only.
提供执行流水线的 before/after 钩子机制。
钩子与事件不同：钩子可以修改执行上下文（拦截/修改数据），事件仅做通知。
"""

from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("ai.hooks")

# Hook handler type / 钩子处理器类型
HookHandler = Callable[..., Coroutine[Any, Any, Any]]


class HookPoint:
    """
    Hook Point Enum / 钩子点枚举

    Defines injection points in the execution pipeline.
    Hooks differ from events: BEFORE_* hooks can modify parameters or block operations (blocked=True),
    AFTER_* hooks can modify return results or trigger subsequent operations.
    定义执行流水线中可注入钩子的位置。
    钩子与事件不同：BEFORE_* 钩子可修改参数或阻止操作（blocked=True），
    AFTER_* 钩子可修改返回结果或触发后续操作。

    Parameter conventions / 参数约定：
      - All hooks receive tenant_id / 所有钩子均接收 tenant_id
      - BEFORE_* hooks can return {"blocked": True, "block_reason": "..."} to block operations / BEFORE_* 钩子可返回阻止操作
      - BEFORE_* hooks can return modified parameter fields to override original values / BEFORE_* 钩子可返回修改后的参数字段来覆盖原始值
      - AFTER_* hooks can return modified result fields / AFTER_* 钩子可返回修改后的 result 字段
    """

    # ── Before/After Execution (Dispatcher layer) / 执行前后（Dispatcher 层） ──
    # params: tenant_id, agent_id, execution_mode, request
    BEFORE_EXECUTE = "before_execute"
    # params: tenant_id, agent_id, result
    AFTER_EXECUTE = "after_execute"

    # ── Message Processing / 消息处理 ──
    # params: tenant_id, conversation_id, role, content | 可修改 content
    BEFORE_MESSAGE_SAVE = "before_message_save"
    # params: tenant_id, conversation_id, message_id, role, content
    AFTER_MESSAGE_SAVE = "after_message_save"

    # ── Tool Call (Sandbox layer) / 工具调用（Sandbox 层） ──
    # params: tenant_id, agent_id, tool_name, arguments, definition | 可修改 arguments
    BEFORE_TOOL_CALL = "before_tool_call"
    # params: tenant_id, agent_id, tool_name, result
    AFTER_TOOL_CALL = "after_tool_call"

    # ── LLM Call / LLM 调用 ──
    # params: tenant_id, agent_id, model, messages, config | 可修改 messages, config
    BEFORE_LLM_CALL = "before_llm_call"
    # params: tenant_id, agent_id, model, response, usage
    AFTER_LLM_CALL = "after_llm_call"

    # ── Context Building / 上下文构建 ──
    # params: tenant_id, agent_id, messages | 可修改 messages
    BEFORE_CONTEXT_BUILD = "before_context_build"
    # params: tenant_id, agent_id, messages, system_prompt | 可修改 system_prompt
    AFTER_CONTEXT_BUILD = "after_context_build"

    # ── Skill Resolution (Skill Resolver) / 技能解析（Skill Resolver） ──
    # params: tenant_id, agent_id, skill_packages | 可修改 skill_packages（注入额外技能）
    BEFORE_SKILL_RESOLVE = "before_skill_resolve"
    # params: tenant_id, agent_id, tool_definitions | 可修改 tool_definitions
    AFTER_SKILL_RESOLVE = "after_skill_resolve"

    # ── Skill CRUD / 技能 CRUD ──
    # params: tenant_id, skill_data | 可修改 skill_data, 可阻止
    BEFORE_SKILL_CREATE = "before_skill_create"
    # params: tenant_id, skill_id, skill_data
    AFTER_SKILL_CREATE = "after_skill_create"
    # params: tenant_id, skill_id, updates | 可修改 updates, 可阻止
    BEFORE_SKILL_UPDATE = "before_skill_update"
    # params: tenant_id, skill_id, updates
    AFTER_SKILL_UPDATE = "after_skill_update"
    # params: tenant_id, skill_id | 可阻止
    BEFORE_SKILL_DELETE = "before_skill_delete"
    # params: tenant_id, skill_id
    AFTER_SKILL_DELETE = "after_skill_delete"

    # ── Agent CRUD / 智能体 CRUD ──
    # params: tenant_id, agent_data | 可修改 agent_data, 可阻止
    BEFORE_AGENT_CREATE = "before_agent_create"
    # params: tenant_id, agent_id, agent_data
    AFTER_AGENT_CREATE = "after_agent_create"
    # params: tenant_id, agent_id, updates | 可修改 updates, 可阻止
    BEFORE_AGENT_UPDATE = "before_agent_update"
    # params: tenant_id, agent_id, updates
    AFTER_AGENT_UPDATE = "after_agent_update"
    # params: tenant_id, agent_id | 可阻止
    BEFORE_AGENT_DELETE = "before_agent_delete"
    # params: tenant_id, agent_id
    AFTER_AGENT_DELETE = "after_agent_delete"

    # ── Chat / 对话（Chat） ──
    # params: tenant_id, agent_id, messages, config | 可修改 messages, config（注入 system prompt 等）
    BEFORE_AGENT_CHAT = "before_agent_chat"
    # params: tenant_id, agent_id, response | 可修改 response
    AFTER_AGENT_CHAT = "after_agent_chat"
    # params: tenant_id, agent_id, title | 可修改 title
    BEFORE_CONVERSATION_CREATE = "before_conversation_create"
    # params: tenant_id, agent_id, conversation_id
    AFTER_CONVERSATION_CREATE = "after_conversation_create"

    # ── Model Call (Gateway layer) / 模型调用（Gateway 层） ──
    # params: tenant_id, provider, model, prompt, parameters | 可修改 prompt, parameters
    BEFORE_MODEL_CALL = "before_model_call"
    # params: tenant_id, provider, model, response, token_usage | 可修改 response
    AFTER_MODEL_CALL = "after_model_call"

    # ── Knowledge Base / 知识库 ──
    # params: tenant_id, query, kb_ids, top_k | 可修改 query, top_k
    BEFORE_KB_SEARCH = "before_kb_search"
    # params: tenant_id, query, results | 可修改 results（过滤/重排）
    AFTER_KB_SEARCH = "after_kb_search"

    # ── Data Intelligence (SQL) / 数据智能（SQL） ──
    # params: tenant_id, sql, datasource_id | 可修改 sql, 可阻止
    BEFORE_SQL_EXECUTE = "before_sql_execute"
    # params: tenant_id, sql, rows, columns | 可修改 rows（脱敏/过滤）
    AFTER_SQL_EXECUTE = "after_sql_execute"


class _HookEntry:
    """Hook registration entry / 钩子注册条目"""

    __slots__ = ("handler", "priority")

    def __init__(self, handler: HookHandler, priority: int = 0):
        self.handler = handler
        self.priority = priority


class HookRegistry:
    """
    Hook Registry / 钩子注册表

    Manages handlers for each hook point in the execution pipeline.
    管理执行流水线中各个钩子点的处理器。

    Usage / 使用示例：
        hooks = HookRegistry.get_instance()
        hooks.register(HookPoint.BEFORE_EXECUTE, my_quota_check, priority=-10)

        # Trigger in execution engine / 在执行引擎中触发
        context = await hooks.trigger(HookPoint.BEFORE_EXECUTE, context=ctx)
    """

    _instance: "HookRegistry | None" = None

    def __init__(self) -> None:
        self._hooks: dict[str, list[_HookEntry]] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> "HookRegistry":
        """Get singleton instance / 获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing only) / 重置单例（仅用于测试）"""
        cls._instance = None

    def register(
        self,
        hook_point: str,
        handler: HookHandler,
        priority: int = 0,
    ) -> None:
        """
        Register hook.
        注册钩子。

        Args:
            hook_point: Hook point (HookPoint constant) / 钩子点（HookPoint 常量）
            handler: Async handler function, receives **kwargs and can return modified context / 异步处理函数
            priority: Priority (lower number executes first) / 优先级（数值越小越先执行）
        """
        entry = _HookEntry(handler, priority)
        entries = self._hooks[hook_point]
        entries.append(entry)
        entries.sort(key=lambda e: e.priority)

        logger.debug(
            "Hook registered: {} -> {} (priority={})",
            hook_point,
            handler.__qualname__,
            priority,
        )

    def unregister(
        self,
        hook_point: str,
        handler: HookHandler,
    ) -> bool:
        """
        Unregister hook.
        移除钩子。

        Args:
            hook_point: Hook point / 钩子点
            handler: Handler function to remove / 要移除的处理函数

        Returns:
            Whether removal succeeded / 是否成功移除
        """
        entries = self._hooks.get(hook_point, [])
        before = len(entries)
        self._hooks[hook_point] = [
            e for e in entries if e.handler is not handler
        ]
        return before - len(self._hooks[hook_point]) > 0

    async def trigger(
        self,
        hook_point: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Trigger hook.
        触发钩子。

        All handlers registered at this hook point are executed serially by priority.
        Each handler receives current kwargs and can return a modified dict to update context.
        If a handler returns None, context remains unchanged.
        所有注册在该钩子点的处理器按优先级串行执行。
        每个处理器接收当前 kwargs，可返回修改后的 dict 来更新上下文。
        如果处理器返回 None，上下文不变。

        Args:
            hook_point: Hook point / 钩子点
            **kwargs: Context parameters passed to handlers / 传递给处理器的上下文参数

        Returns:
            Processed context dictionary / 处理后的上下文字典
        """
        entries = self._hooks.get(hook_point, [])
        context = dict(kwargs)

        for entry in entries:
            try:
                result = await entry.handler(**context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception as exc:
                logger.error(
                    "Hook error: {} in {}: {}",
                    hook_point,
                    entry.handler.__qualname__,
                    str(exc),
                    exc_info=True,
                )

        return context

    def has_hooks(self, hook_point: str) -> bool:
        """Check if hook point has registered handlers / 检查钩子点是否有注册的处理器"""
        return len(self._hooks.get(hook_point, [])) > 0

    def clear(self) -> None:
        """Clear all hooks (for testing only) / 清除所有钩子（仅用于测试）"""
        self._hooks.clear()


# Global convenience function / 全局便捷函数
def get_hook_registry() -> HookRegistry:
    """Get global hook registry instance / 获取全局钩子注册表实例"""
    return HookRegistry.get_instance()


__all__ = [
    "HookPoint",
    "HookHandler",
    "HookRegistry",
    "get_hook_registry",
]
