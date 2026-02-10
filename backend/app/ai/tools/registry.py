"""
工具注册表

管理工具定义，支持注册、发现、校验和 OpenAI 格式转换。
按租户隔离，避免多租户同名工具互相覆盖。
"""

import threading
from collections import OrderedDict
from typing import Any

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.tool.registry")

# 租户实例上限，超出后淘汰最久未访问的实例
MAX_TENANT_INSTANCES = 1000


class ToolRegistry:
    """
    工具注册表

    支持全局单例（系统工具）和 per-tenant 实例（租户自定义工具）。
    租户实例采用 LRU 淘汰策略，上限 MAX_TENANT_INSTANCES。

    使用示例:
        registry = get_tool_registry(tenant_id=1)
        registry.register(my_tool_definition)
        tools = registry.resolve_agent_tools(agent.tool_bindings)
    """

    _instance: "ToolRegistry | None" = None
    _tenant_instances: OrderedDict[int, "ToolRegistry"] = OrderedDict()
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    @classmethod
    def get_instance(cls, tenant_id: int | None = None) -> "ToolRegistry":
        """
        获取注册表实例

        Args:
            tenant_id: 租户 ID。为 None 时返回全局单例。

        Returns:
            ToolRegistry 实例（per-tenant 或全局）
        """
        if tenant_id is None:
            if cls._instance is None:
                with cls._lock:
                    if cls._instance is None:
                        cls._instance = cls()
            return cls._instance

        with cls._lock:
            if tenant_id in cls._tenant_instances:
                # LRU: 移到末尾表示最近访问
                cls._tenant_instances.move_to_end(tenant_id)
                return cls._tenant_instances[tenant_id]

            instance = cls()
            cls._tenant_instances[tenant_id] = instance

            # LRU 淘汰：超出上限时移除最久未访问的实例
            while len(cls._tenant_instances) > MAX_TENANT_INSTANCES:
                evicted_id, _ = cls._tenant_instances.popitem(last=False)
                logger.debug(
                    "Evicted tenant registry: tenant_id=%d (capacity=%d)",
                    evicted_id,
                    MAX_TENANT_INSTANCES,
                )

            return instance

    @classmethod
    def reset(cls, tenant_id: int | None = None) -> None:
        """
        重置实例（仅用于测试）

        Args:
            tenant_id: 为 None 时重置全局 + 所有租户实例
        """
        with cls._lock:
            if tenant_id is None:
                cls._instance = None
                cls._tenant_instances.clear()
            else:
                cls._tenant_instances.pop(tenant_id, None)

    # ========================================
    # 注册与查询
    # ========================================

    def register(self, definition: ToolDefinition) -> None:
        """
        注册工具

        Args:
            definition: 工具定义
        """
        self._tools[definition.name] = definition
        logger.debug(
            "Tool registered: %s (type=%s)",
            definition.name,
            definition.tool_type,
        )

    def unregister(self, name: str) -> bool:
        """
        移除工具

        Args:
            name: 工具名称

        Returns:
            是否成功移除
        """
        return self._tools.pop(name, None) is not None

    def get(self, name: str) -> ToolDefinition | None:
        """
        获取工具定义

        Args:
            name: 工具名称

        Returns:
            ToolDefinition 或 None
        """
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """检查工具是否已注册"""
        return name in self._tools

    def list_all(self) -> list[ToolDefinition]:
        """获取所有已注册工具"""
        return list(self._tools.values())

    # ========================================
    # Agent 工具解析
    # ========================================

    def resolve_agent_tools(
        self,
        tool_bindings: list[dict[str, Any]] | None,
    ) -> list[ToolDefinition]:
        """
        从 Agent.tool_bindings 解析工具列表

        tool_bindings 格式示例:
            [
                {"name": "weather_api", "enabled": true},
                {"name": "calculate", "enabled": true, "config": {...}},
            ]

        如果 binding 中的 name 在注册表中存在，使用注册表定义。
        如果 binding 包含完整定义（含 tool_type + parameters），直接构造。

        Args:
            tool_bindings: Agent 的工具绑定 JSON

        Returns:
            解析后的工具定义列表
        """
        if not tool_bindings:
            return []

        definitions: list[ToolDefinition] = []

        for binding in tool_bindings:
            name = binding.get("name", "")
            if not name:
                continue

            enabled = binding.get("enabled", True)
            if not enabled:
                continue

            # 优先从注册表获取
            registered = self._tools.get(name)
            if registered:
                # 允许 binding 覆盖 config 和 timeout
                override_config = binding.get("config")
                override_timeout = binding.get("timeout")
                if override_config or override_timeout is not None:
                    merged = ToolDefinition(
                        name=registered.name,
                        description=registered.description,
                        tool_type=registered.tool_type,
                        parameters=registered.parameters,
                        config={**registered.config, **(override_config or {})},
                        enabled=True,
                        timeout=override_timeout if override_timeout is not None else registered.timeout,
                    )
                    definitions.append(merged)
                else:
                    definitions.append(registered)
                continue

            # 未注册：尝试从 binding 构造
            tool_type = binding.get("tool_type", "")
            description = binding.get("description", "")
            raw_params = binding.get("parameters", [])
            config = binding.get("config", {})

            if tool_type and description:
                params = [
                    ToolParameter(
                        name=p.get("name", ""),
                        type=p.get("type", "string"),
                        description=p.get("description", ""),
                        required=p.get("required", False),
                        default=p.get("default"),
                        enum=p.get("enum"),
                    )
                    for p in raw_params
                    if p.get("name")
                ]
                timeout = binding.get("timeout", 30)
                definitions.append(ToolDefinition(
                    name=name,
                    description=description,
                    tool_type=tool_type,
                    parameters=params,
                    config=config,
                    enabled=True,
                    timeout=timeout,
                ))
            else:
                logger.warning(
                    "Tool '%s' not found in registry and binding incomplete",
                    name,
                )

        return definitions

    # ========================================
    # OpenAI 格式转换
    # ========================================

    @staticmethod
    def to_openai_tools(
        definitions: list[ToolDefinition],
    ) -> list[dict[str, Any]]:
        """
        批量转换为 OpenAI function calling 格式

        Args:
            definitions: 工具定义列表

        Returns:
            OpenAI tools schema list
        """
        return [d.to_openai_schema() for d in definitions if d.enabled]

    # ========================================
    # 校验
    # ========================================

    def validate_tool_call(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        校验工具调用参数合法性

        Args:
            name: 工具名称
            arguments: LLM 传入的参数

        Returns:
            (is_valid, error_message) 元组
        """
        definition = self._tools.get(name)
        if not definition:
            return False, f"Tool '{name}' not registered"

        if not definition.enabled:
            return False, f"Tool '{name}' is disabled"

        # 检查必填参数
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False, f"Missing required parameter: {param.name}"

        return True, ""

    def clear(self) -> None:
        """清除所有工具（仅用于测试）"""
        self._tools.clear()


# 全局便捷函数
def get_tool_registry(tenant_id: int | None = None) -> ToolRegistry:
    """
    获取工具注册表实例

    Args:
        tenant_id: 租户 ID。为 None 时返回全局单例，
                   提供时返回该租户的隔离实例。
    """
    return ToolRegistry.get_instance(tenant_id)


__all__ = [
    "ToolRegistry",
    "get_tool_registry",
]
