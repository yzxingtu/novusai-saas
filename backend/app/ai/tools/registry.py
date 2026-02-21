"""
工具注册表（已废弃）

.. deprecated::
    此模块已被 Skill 架构替代。新代码请使用：
    - ``app.ai.skills.resolver.SkillResolver`` 解析 Skill → ToolDefinition
    - ``app.ai.tools.types.to_openai_tools()`` 转换为 OpenAI 格式
    仅保留供旧插件兼容使用，将在后续版本中移除。
"""

import threading
from collections import OrderedDict
from typing import Any

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import ToolTypeEnum

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
        tools = registry.list_all()
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

    def list_names(self) -> list[str]:
        """获取所有已注册工具名称"""
        return list(self._tools.keys())

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
            return False, _("tool.error.not_registered", name=name)

        if not definition.enabled:
            return False, _("tool.error.disabled", name=name)

        # 检查必填参数
        for param in definition.parameters:
            if param.required and param.name not in arguments:
                return False, _("tool.error.missing_param", param=param.name)

        return True, ""

    def clear(self) -> None:
        """清除所有工具（仅用于测试）"""
        self._tools.clear()

    # ========================================
    # 平台工具自动注册
    # ========================================

    def register_platform_tools(
        self,
        agent: Any = None,
        table_descriptions: list[tuple[str, str]] | None = None,
        crud_allowed_tables: dict[str, list[tuple[str, str]]] | None = None,
    ) -> None:
        """
        将平台内置工具注册为 ToolDefinition

        - text_to_sql: 注册为单个 "data_query" 工具
        - data_create / data_update / data_delete: 基于 ai_table_policies 动态注册

        通过 agent.context_config.data_intelligence_enabled 控制是否注册。

        Args:
            agent: Agent 模型实例（可选，用于检查开关）
            table_descriptions: 从 ai_table_policies 加载的 (table_name, label) 列表
        """
        # 检查 Agent 是否启用了数据智能
        if agent:
            ctx = agent.context_config or {}
            if not ctx.get("data_intelligence_enabled", False):
                return

        # 1. 注册 text_to_sql 平台工具（始终覆盖，确保描述最新）
        if table_descriptions:
            table_list = ", ".join(
                f"{name}({label})" for name, label in table_descriptions
            )
        else:
            table_list = "(no tables configured)"
        self.register(ToolDefinition(
            name="data_query",
            description=(
                "Query the database using natural language. "
                "The system will automatically generate safe SQL and return results. "
                f"Available tables: {table_list}. "
                "IMPORTANT: You MUST use this tool for ANY question about data counts, "
                "totals, statistics, listings, or aggregations — including tenant counts, "
                "user counts, agent counts, conversation counts, usage stats, etc. "
                "Do NOT use other action tools for counting or statistical questions."
            ),
            tool_type=ToolTypeEnum.TEXT_TO_SQL.value,
            parameters=[
                ToolParameter(
                    name="question",
                    type="string",
                    description="The data question in natural language",
                    required=True,
                ),
            ],
            config={},
            enabled=True,
            timeout=60,
        ))

        # 2. 注册通用 CRUD 工具（基于 ai_table_policies 中的 CRUD 开关）
        if table_descriptions:
            self._register_crud_tools(
                table_descriptions,
                crud_allowed_tables or {},
            )

        registered_names = list(self._tools.keys())
        logger.info(
            "Platform tools registered: total=%d tools=%s",
            len(self._tools), registered_names,
        )

    def _register_crud_tools(
        self,
        table_descriptions: list[tuple[str, str]],
        crud_allowed_tables: dict[str, list[tuple[str, str]]],
    ) -> None:
        """根据策略注册通用 CRUD 工具（create/update/delete）

        仅当至少一个表启用了对应操作时才注册该工具。
        工具描述中只列出实际允许该操作的表，防止 LLM 在不允许的表上重复尝试。
        实际执行时由 executor 层根据策略做表级检查。
        """
        # data_create
        create_tables = crud_allowed_tables.get("create", [])
        if create_tables:
            create_list = ", ".join(f"{n}({l})" for n, l in create_tables)
            self.register(ToolDefinition(
                name="data_create",
                description=(
                    "Create a new record in a database table. "
                    "First call without 'confirmed' to get a preview; "
                    "then call again with confirmed=true after user approval. "
                    "ONLY these tables allow creation: "
                    f"{create_list}. "
                    "Do NOT attempt to create records in any other table."
                ),
                tool_type=ToolTypeEnum.DATA_CREATE.value,
                parameters=[
                    ToolParameter(name="table_name", type="string",
                                  description="Target table name", required=True),
                    ToolParameter(name="data", type="object",
                                  description="Record data as {field: value}", required=True),
                    ToolParameter(name="confirmed", type="boolean",
                                  description="Set to true after user confirms"),
                ],
                config={},
                enabled=True,
                timeout=30,
            ))

        # data_update
        update_tables = crud_allowed_tables.get("update", [])
        if update_tables:
            update_list = ", ".join(f"{n}({l})" for n, l in update_tables)
            self.register(ToolDefinition(
                name="data_update",
                description=(
                    "Update an existing record in a database table. "
                    "First call without 'confirmed' to see a diff preview; "
                    "then call again with confirmed=true after user approval. "
                    "ONLY these tables allow updates: "
                    f"{update_list}. "
                    "Do NOT attempt to update records in any other table."
                ),
                tool_type=ToolTypeEnum.DATA_UPDATE.value,
                parameters=[
                    ToolParameter(name="table_name", type="string",
                                  description="Target table name", required=True),
                    ToolParameter(name="id", type="integer",
                                  description="Record ID to update", required=True),
                    ToolParameter(name="data", type="object",
                                  description="Fields to update as {field: value}", required=True),
                    ToolParameter(name="confirmed", type="boolean",
                                  description="Set to true after user confirms"),
                ],
                config={},
                enabled=True,
                timeout=30,
            ))

        # data_delete
        delete_tables = crud_allowed_tables.get("delete", [])
        if delete_tables:
            delete_list = ", ".join(f"{n}({l})" for n, l in delete_tables)
            self.register(ToolDefinition(
                name="data_delete",
                description=(
                    "Soft-delete a record from a database table. "
                    "First call without 'confirmed' to see record details; "
                    "then call again with confirmed=true after user explicitly confirms. "
                    "ONLY these tables allow deletion: "
                    f"{delete_list}. "
                    "Do NOT attempt to delete records in any other table."
                ),
                tool_type=ToolTypeEnum.DATA_DELETE.value,
                parameters=[
                    ToolParameter(name="table_name", type="string",
                                  description="Target table name", required=True),
                    ToolParameter(name="id", type="integer",
                                  description="Record ID to delete", required=True),
                    ToolParameter(name="confirmed", type="boolean",
                                  description="Set to true after user confirms"),
                ],
                config={},
                enabled=True,
                timeout=30,
            ))


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
