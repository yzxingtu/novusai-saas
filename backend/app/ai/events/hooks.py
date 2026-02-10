"""
钩子系统

提供执行流水线的 before/after 钩子机制
钩子与事件不同：钩子可以修改执行上下文（拦截/修改数据），事件仅做通知
"""

from collections import defaultdict
from typing import Any, Callable, Coroutine

from app.core.logging import LogManager

logger = LogManager.get_logger("ai.hooks")

# 钩子处理器类型
HookHandler = Callable[..., Coroutine[Any, Any, Any]]


class HookPoint:
    """
    钩子点枚举

    定义执行流水线中可注入钩子的位置
    """

    # 执行前后
    BEFORE_EXECUTE = "before_execute"
    AFTER_EXECUTE = "after_execute"

    # 消息处理前后
    BEFORE_MESSAGE_SAVE = "before_message_save"
    AFTER_MESSAGE_SAVE = "after_message_save"

    # 工具调用前后
    BEFORE_TOOL_CALL = "before_tool_call"
    AFTER_TOOL_CALL = "after_tool_call"

    # LLM 调用前后
    BEFORE_LLM_CALL = "before_llm_call"
    AFTER_LLM_CALL = "after_llm_call"

    # 上下文构建
    BEFORE_CONTEXT_BUILD = "before_context_build"
    AFTER_CONTEXT_BUILD = "after_context_build"


class _HookEntry:
    """钩子注册条目"""

    __slots__ = ("handler", "priority")

    def __init__(self, handler: HookHandler, priority: int = 0):
        self.handler = handler
        self.priority = priority


class HookRegistry:
    """
    钩子注册表

    管理执行流水线中各个钩子点的处理器

    使用示例：
        hooks = HookRegistry.get_instance()
        hooks.register(HookPoint.BEFORE_EXECUTE, my_quota_check, priority=-10)

        # 在执行引擎中触发
        context = await hooks.trigger(HookPoint.BEFORE_EXECUTE, context=ctx)
    """

    _instance: "HookRegistry | None" = None

    def __init__(self) -> None:
        self._hooks: dict[str, list[_HookEntry]] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> "HookRegistry":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None

    def register(
        self,
        hook_point: str,
        handler: HookHandler,
        priority: int = 0,
    ) -> None:
        """
        注册钩子

        Args:
            hook_point: 钩子点（HookPoint 常量）
            handler: 异步处理函数，接收 **kwargs 并可返回修改后的上下文
            priority: 优先级（数值越小越先执行）
        """
        entry = _HookEntry(handler, priority)
        entries = self._hooks[hook_point]
        entries.append(entry)
        entries.sort(key=lambda e: e.priority)

        logger.debug(
            "Hook registered: %s -> %s (priority=%d)",
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
        移除钩子

        Args:
            hook_point: 钩子点
            handler: 要移除的处理函数

        Returns:
            是否成功移除
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
        触发钩子

        所有注册在该钩子点的处理器按优先级串行执行。
        每个处理器接收当前 kwargs，可返回修改后的 dict 来更新上下文。
        如果处理器返回 None，上下文不变。

        Args:
            hook_point: 钩子点
            **kwargs: 传递给处理器的上下文参数

        Returns:
            处理后的上下文字典
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
                    "Hook error: %s in %s: %s",
                    hook_point,
                    entry.handler.__qualname__,
                    str(exc),
                    exc_info=True,
                )

        return context

    def has_hooks(self, hook_point: str) -> bool:
        """检查钩子点是否有注册的处理器"""
        return len(self._hooks.get(hook_point, [])) > 0

    def clear(self) -> None:
        """清除所有钩子（仅用于测试）"""
        self._hooks.clear()


# 全局便捷函数
def get_hook_registry() -> HookRegistry:
    """获取全局钩子注册表实例"""
    return HookRegistry.get_instance()


__all__ = [
    "HookPoint",
    "HookHandler",
    "HookRegistry",
    "get_hook_registry",
]
