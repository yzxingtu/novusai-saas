"""
Netdisk 技能解析器

为 plugin.yaml extensions.skills 中声明的 toolkit 技能提供 resolve() 入口。
"""

from app.ai.tools.types import ToolDefinition, ToolParameter


def resolve(skill, config: dict) -> list[ToolDefinition]:
    """
    将网盘 Skill 解析为 ToolDefinition 列表。

    Args:
        skill: Skill 模型实例（plugin.yaml 声明时为 None）
        config: 合并后的配置

    Returns:
        ToolDefinition 列表（list_files + search_files 两个工具）
    """
    timeout = config.get("timeout", 15)

    return [
        ToolDefinition(
            name="list_files",
            description=(
                "List files and folders in the enterprise netdisk. "
                "Returns name, type, size, mime type and last updated time. "
                "Supports optional file type filter: pdf/image/video/audio/doc."
            ),
            tool_type="toolkit",
            parameters=[
                ToolParameter(
                    name="folder_path",
                    type="string",
                    description="Folder path to list, default '/' for root",
                    required=False,
                ),
                ToolParameter(
                    name="file_type",
                    type="string",
                    description="Filter by type: pdf/image/video/audio/doc, empty=all",
                    required=False,
                ),
            ],
            config=config,
            enabled=True,
            timeout=timeout,
        ),
        ToolDefinition(
            name="search_files",
            description=(
                "Search files in the enterprise netdisk by filename keyword. "
                "Returns matching files with full path info."
            ),
            tool_type="toolkit",
            parameters=[
                ToolParameter(
                    name="keyword",
                    type="string",
                    description="Keyword to search in filenames",
                    required=True,
                ),
                ToolParameter(
                    name="file_type",
                    type="string",
                    description="Filter by type: pdf/image/video/audio/doc, empty=all",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Max results (1-50, default 10)",
                    required=False,
                ),
            ],
            config=config,
            enabled=True,
            timeout=timeout,
        ),
    ]
