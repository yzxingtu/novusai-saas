"""实时天气技能解析器 / Real-time weather skill resolver.

将插件 Skill 解析为 ToolDefinition。
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
                "Get real-time current weather for a city, county, district, region, "
                "or scenic area. Use this for requests like '怀化市天气', '凤凰县天气', "
                "'今天怀化天气怎么样'. Returns temperature, weather condition, humidity, "
                "wind speed and UV index. Supports both Chinese and English place names."
            ),
            tool_type="toolkit",
            parameters=[
                ToolParameter(
                    name="city",
                    type="string",
                    description=(
                        "Place name, supports city/county/district/region/scenic area "
                        "in Chinese or English (e.g. 'Shanghai', '上海', '怀化市', '凤凰县', 'Tokyo')"
                    ),
                    required=True,
                ),
            ],
            config=config,
            enabled=True,
            timeout=timeout,
            semantic_family="weather",
            semantic_tags=[
                "天气查询",
                "当前天气",
                "实时天气",
                "weather",
                "current weather",
            ],
        ),
        ToolDefinition(
            name="get_weather_forecast",
            description=(
                "Get multi-day weather forecast for a city, county, district, region, "
                "or scenic area. Use this for requests like '凤凰县未来七天天气' or "
                "'怀化市明天天气'. Returns daily high/low temperature and weather condition. "
                "Supports 1-7 days forecast."
            ),
            tool_type="toolkit",
            parameters=[
                ToolParameter(
                    name="city",
                    type="string",
                    description=(
                        "Place name, supports city/county/district/region/scenic area "
                        "in Chinese or English (e.g. 'Shanghai', '上海', '怀化市', '凤凰县', 'Tokyo')"
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
            semantic_family="weather",
            semantic_tags=[
                "天气预报",
                "未来天气",
                "weather",
                "weather forecast",
                "forecast",
            ],
        ),
    ]
