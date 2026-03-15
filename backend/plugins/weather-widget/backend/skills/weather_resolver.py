"""实时天气技能解析器 / Parse.

将 weather_widget 类型的 Skill 解析为 ToolDefinition。
提供两个工具：get_current_weather（当前天气）+ get_weather_forecast（多日预报）。"""

from app.ai.tools.types import ToolDefinition, ToolParameter


def resolve(skill, config: dict) -> list[ToolDefinition]:
    """将天气 Skill 解析为 ToolDefinition 列表 / Parse weather Skill into ToolDefinition list.

    Args:
        skill: Skill 模型实例
        config: 合并后的配置

    Returns:
        ToolDefinition 列表（2 个工具）
    """
    timeout = config.get("timeout", 15)

    return [
        ToolDefinition(
            name="get_current_weather",
            description=(
                "Get real-time current weather for a city. "
                "Returns temperature, weather condition, humidity, "
                "wind speed and UV index. "
                "Supports both Chinese and English city names."
            ),
            tool_type="toolkit",
            parameters=[
                ToolParameter(
                    name="city",
                    type="string",
                    description=(
                        "City name, supports Chinese and English "
                        "(e.g. 'Shanghai', '上海', 'Beijing', 'Tokyo')"
                    ),
                    required=True,
                ),
            ],
            config=config,
            enabled=True,
            timeout=timeout,
        ),
        ToolDefinition(
            name="get_weather_forecast",
            description=(
                "Get multi-day weather forecast for a city. "
                "Returns daily high/low temperature and weather condition. "
                "Supports 1-7 days forecast."
            ),
            tool_type="toolkit",
            parameters=[
                ToolParameter(
                    name="city",
                    type="string",
                    description=(
                        "City name, supports Chinese and English "
                        "(e.g. 'Shanghai', '上海', 'Beijing', 'Tokyo')"
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="Number of forecast days (1-7, default: 3)",
                    required=False,
                ),
            ],
            config=config,
            enabled=True,
            timeout=timeout,
        ),
    ]
