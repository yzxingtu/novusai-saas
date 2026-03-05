"""
实时天气工具执行器

调用 Open-Meteo API 获取真实天气数据，支持当前天气和多日预报两个工具。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext


def _get_open_meteo():
    """动态加载 open_meteo 模块（插件名含连字符，需 importlib）"""
    import importlib.util
    import sys
    from pathlib import Path

    module_name = "plugins.weather-widget.backend.open_meteo"
    if module_name in sys.modules:
        return sys.modules[module_name]

    module_file = Path(__file__).parent.parent / "open_meteo.py"
    spec = importlib.util.spec_from_file_location(module_name, module_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_file}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class WeatherWidgetExecutor(BaseToolExecutor):
    """实时天气执行器（调用 Open-Meteo API）"""

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        _definition = definition
        return bool(arguments.get("city"))

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        _context = context
        start = time.perf_counter()

        city = arguments.get("city", "").strip()
        if not city:
            err_msg = _("plugin.weather-widget.error.city_required")
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=err_msg,
                output=err_msg,
                duration_ms=0,
            )

        tool_name = definition.name

        try:
            if tool_name == "get_current_weather":
                output = await self._get_current(city)
            elif tool_name == "get_weather_forecast":
                days = arguments.get("days", 3)
                if not isinstance(days, int):
                    try:
                        days = int(days)
                    except (ValueError, TypeError):
                        days = 3
                output = await self._get_forecast(city, days)
            else:
                err_msg = _("plugin.weather-widget.error.unknown_tool").format(
                    tool_name=tool_name,
                )
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    success=False,
                    error=err_msg,
                    output=err_msg,
                    duration_ms=int((time.perf_counter() - start) * 1000),
                )

            duration_ms = int((time.perf_counter() - start) * 1000)
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            err_msg = _("plugin.weather-widget.error.fetch_failed").format(
                city=city,
                error=str(exc),
            )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=False,
                error=err_msg,
                output=err_msg,
                duration_ms=duration_ms,
            )

    async def _resolve_city(self, city: str) -> tuple[float, float, str]:
        """
        将城市名解析为坐标。

        Returns:
            (latitude, longitude, resolved_city_name)

        Raises:
            ValueError: 城市未找到
        """
        open_meteo = _get_open_meteo()
        results = await open_meteo.search_city(city, count=1)
        if not results:
            raise ValueError(
                _("plugin.weather-widget.error.city_not_found_with_name").format(
                    city=city,
                )
            )

        hit = results[0]
        resolved_name = hit.get("name", city)
        return hit["latitude"], hit["longitude"], resolved_name

    async def _get_current(self, city: str) -> str:
        """获取当前天气并格式化输出"""
        open_meteo = _get_open_meteo()
        lat, lon, name = await self._resolve_city(city)
        weather = await open_meteo.get_current_weather(lat, lon)

        lines = [
            f"Current weather for {name}:",
            f"  Temperature: {weather['temperature']}°C",
            f"  Condition: {weather['weather_text_en']} ({weather['weather_text_zh']})",
            f"  Humidity: {weather['humidity']}%",
            f"  Wind Speed: {weather['wind_speed']} km/h",
            f"  UV Index: {weather['uv_index']}",
        ]
        return "\n".join(lines)

    async def _get_forecast(self, city: str, days: int) -> str:
        """获取多日预报并格式化输出"""
        open_meteo = _get_open_meteo()
        lat, lon, name = await self._resolve_city(city)
        forecast = await open_meteo.get_forecast(lat, lon, days)

        lines = [f"{days}-day weather forecast for {name}:"]
        for day in forecast:
            lines.append(
                f"  {day['date']}: "
                f"{day['weather_text_en']} ({day['weather_text_zh']}), "
                f"High {day['temp_max']}°C / Low {day['temp_min']}°C"
            )
        return "\n".join(lines)
