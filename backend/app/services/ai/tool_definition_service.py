"""
工具定义 Service
"""

from typing import Any, Dict, List

from app.ai.tools.registry import get_tool_registry
from app.ai.tools.types import ToolDefinition as ToolDefinitionDTO, ToolParameter
from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import ToolTypeEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.tool_definition import ToolDefinition
from app.repositories.ai.tool_definition_repository import ToolDefinitionRepository

logger = LogManager.get_logger("ai.tool.service")


class ToolDefinitionService(TenantService[ToolDefinition, ToolDefinitionRepository]):
    """
    工具定义 Service

    提供工具定义的创建、更新、删除、同步注册表等业务逻辑
    """

    model = ToolDefinition
    repository_class = ToolDefinitionRepository

    async def _before_create(self, data: Dict[str, Any]) -> None:
        """创建前校验：名称唯一性、类型合法性"""
        await super()._before_create(data)

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name)
            if existing:
                raise BusinessException(message=_("tool_definition.error.name_exists"))

        # 校验工具类型
        tool_type = data.get("type", ToolTypeEnum.HTTP.value)
        valid_types = [e.value for e in ToolTypeEnum]
        if tool_type not in valid_types:
            raise BusinessException(message=_("tool_definition.error.invalid_type"))

    async def _before_update(self, id: int, data: Dict[str, Any]) -> None:
        """更新前校验：系统工具不可编辑、名称唯一性"""
        await super()._before_update(id, data)

        tool = await self.repo.get_by_id(id)
        if not tool:
            raise NotFoundException(message=_("tool_definition.error.not_found"))

        if tool.is_system:
            raise BusinessException(message=_("tool_definition.error.system_readonly"))

        name = data.get("name")
        if name:
            existing = await self.repo.get_by_name(name, exclude_id=id)
            if existing:
                raise BusinessException(message=_("tool_definition.error.name_exists"))

    async def _before_delete(self, id: int) -> None:
        """删除前校验：系统工具不可删除"""
        await super()._before_delete(id)

        tool = await self.repo.get_by_id(id)
        if not tool:
            raise NotFoundException(message=_("tool_definition.error.not_found"))

        if tool.is_system:
            raise BusinessException(message=_("tool_definition.error.system_readonly"))

    async def get_active_tools(self) -> List[ToolDefinition]:
        """获取当前租户所有已激活的工具"""
        return await self.repo.get_active_tools()

    async def sync_to_registry(self) -> int:
        """
        将 DB 中已激活工具同步到内存 ToolRegistry

        Returns:
            同步的工具数量
        """
        registry = get_tool_registry(self.tenant_id)
        active_tools = await self.repo.get_active_tools()
        system_tools = await self.repo.get_system_tools()

        all_tools = active_tools + system_tools
        count = 0

        for tool in all_tools:
            # 从 input_schema 构建参数列表
            parameters = self._build_parameters(tool.input_schema or {})

            dto = ToolDefinitionDTO(
                name=tool.name,
                description=tool.description or "",
                parameters=parameters,
                tool_type=tool.type,
                config=tool.config or {},
            )
            registry.register(dto)
            count += 1

        logger.info(
            "Synced %d tools to registry for tenant %d",
            count,
            self.tenant_id,
        )
        return count

    @staticmethod
    def _build_parameters(input_schema: Dict[str, Any]) -> List[ToolParameter]:
        """
        从 JSON Schema 构建 ToolParameter 列表

        input_schema 格式示例:
        {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        }
        """
        properties = input_schema.get("properties", {})
        required = set(input_schema.get("required", []))
        parameters = []

        for name, prop in properties.items():
            parameters.append(ToolParameter(
                name=name,
                type=prop.get("type", "string"),
                description=prop.get("description", ""),
                required=name in required,
                enum=prop.get("enum"),
            ))

        return parameters

    async def test_execute(
        self,
        tool_id: int,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        测试执行工具

        Args:
            tool_id: 工具 ID
            arguments: 测试参数

        Returns:
            包含 success/output/error/duration_ms 的结果字典
        """
        from app.ai.tools.sandbox import ToolSandbox

        tool = await self.repo.get_by_id(tool_id)
        if not tool:
            raise NotFoundException(message=_("tool_definition.error.not_found"))

        # 构建 ToolDefinition DTO
        parameters = self._build_parameters(tool.input_schema or {})
        definition = ToolDefinitionDTO(
            name=tool.name,
            description=tool.description or "",
            parameters=parameters,
            tool_type=tool.type,
            config=tool.config or {},
        )

        # 使用沙箱执行
        sandbox = ToolSandbox(
            tenant_id=self.tenant_id,
            agent_id=0,
        )
        result = await sandbox.execute(
            tool_call_id="test",
            name=tool.name,
            arguments=arguments,
            definitions=[definition],
        )

        return {
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "duration_ms": result.duration_ms,
        }


__all__ = ["ToolDefinitionService"]
