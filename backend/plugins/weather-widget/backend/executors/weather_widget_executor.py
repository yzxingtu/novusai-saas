"""实时天气工具执行器 / Realtime weather tool executor.

通过插件 provider 获取天气数据，支持当前天气和多日预报两个工具。
EN: Fetches weather data through the plugin provider for current weather and
forecast tools."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext


def _get_open_meteo():
    """中文: 通过平台插件模块加载器加载天气 provider。

    EN: Load the weather provider through the platform plugin module loader.
    """
    from app.plugins.module_loader import load_plugin_module

    provider = load_plugin_module("weather-widget", "open_meteo")
    if provider is None:
        raise ImportError("Cannot load weather-widget.open_meteo")
    return provider


class WeatherWidgetExecutor(BaseToolExecutor):
    """实时天气执行器 / Realtime weather executor."""

    @staticmethod
    def _tool_timeout_seconds(definition: ToolDefinition) -> float:
        raw_timeout = getattr(definition, "timeout", None)
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            return 15.0
        return timeout if timeout > 0 else 15.0

    @staticmethod
    def _lookup_timeout_seconds(tool_timeout: float) -> float:
        # Reserve headroom for the weather fetch itself so city resolution
        # cannot consume the whole sandbox timeout budget.
        return max(3.0, min(8.0, tool_timeout - 5.0))

    @staticmethod
    def _remaining_timeout(
        deadline: float | None, *, minimum: float = 0.5
    ) -> float | None:
        if deadline is None:
            return None
        remaining = deadline - time.perf_counter()
        if remaining <= minimum:
            return None
        return remaining

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
        tool_timeout = self._tool_timeout_seconds(definition)
        if tool_name not in {"get_current_weather", "get_weather_forecast"}:
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

        provider = _get_open_meteo()
        configure = getattr(provider, "configure", None)
        if callable(configure):
            configure(getattr(definition, "config", {}) or {})

        try:
            if tool_name == "get_current_weather":
                output = await self._get_current(city, total_timeout=tool_timeout)
            else:
                validate_days = getattr(provider, "validate_forecast_days", None)
                if not callable(validate_days):
                    raise RuntimeError("Weather provider is missing days validation")
                try:
                    days = validate_days(arguments.get("days"), default=3)
                except ValueError:
                    err_msg = _("plugin.weather-widget.error.days_invalid")
                    return ToolResult(
                        tool_call_id=tool_call_id,
                        name=tool_name,
                        success=False,
                        error=err_msg,
                        output=err_msg,
                        duration_ms=int((time.perf_counter() - start) * 1000),
                    )
                output = await self._get_forecast(
                    city,
                    days,
                    total_timeout=tool_timeout,
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

    async def _resolve_city(
        self,
        city: str,
        *,
        total_timeout: float | None = None,
    ) -> tuple[float, float, str]:
        """将城市名解析为坐标。 / Parse.

        Returns:
            (latitude, longitude, resolved_city_name)

        Raises:
            ValueError: 城市未找到"""
        open_meteo = _get_open_meteo()
        deadline = (
            time.perf_counter() + total_timeout
            if total_timeout is not None and total_timeout > 0
            else None
        )
        remaining = self._remaining_timeout(deadline) if deadline is not None else None
        if deadline is not None and remaining is None:
            timeout_value = max(1, int(total_timeout or 1))
            raise TimeoutError(_("tool.error.execution_timeout", timeout=timeout_value))

        try:
            lookup = open_meteo.search_city(city, count=1)
            results = (
                await asyncio.wait_for(lookup, timeout=remaining)
                if remaining is not None
                else await lookup
            )
        except asyncio.TimeoutError:
            timeout_value = max(1, int(total_timeout or 1))
            raise TimeoutError(
                _("tool.error.execution_timeout", timeout=timeout_value)
            ) from None

        if results:
            hit = results[0]
            resolved_name = hit.get("name", city)
            return hit["latitude"], hit["longitude"], resolved_name

        raise ValueError(
            _("plugin.weather-widget.error.city_not_found_with_name").format(
                city=city,
            )
        )

    async def _get_current(
        self,
        city: str,
        *,
        total_timeout: float | None = None,
    ) -> str:
        """获取当前天气并格式化输出 / Get current weather and format output."""
        open_meteo = _get_open_meteo()
        deadline = (
            time.perf_counter() + total_timeout
            if total_timeout is not None and total_timeout > 0
            else None
        )
        lookup_timeout = self._lookup_timeout_seconds(total_timeout or 15.0)
        lat, lon, name = await self._resolve_city(
            city,
            total_timeout=lookup_timeout,
        )
        remaining = self._remaining_timeout(deadline, minimum=1.0)
        weather = (
            await asyncio.wait_for(
                open_meteo.get_current_weather(lat, lon),
                timeout=remaining,
            )
            if remaining is not None
            else await open_meteo.get_current_weather(lat, lon)
        )

        lines = [
            f"Current weather for {name}:",
            f"  Temperature: {weather['temperature']}°C",
            f"  Condition: {weather['weather_text_en']} ({weather['weather_text_zh']})",
            f"  Humidity: {weather['humidity']}%",
            f"  Wind Speed: {weather['wind_speed']} km/h",
            f"  UV Index: {weather['uv_index']}",
        ]
        return "\n".join(lines)

    async def _get_forecast(
        self,
        city: str,
        days: int,
        *,
        total_timeout: float | None = None,
    ) -> str:
        """获取多日预报并格式化输出 / Get multi-day forecast and format output."""
        open_meteo = _get_open_meteo()
        deadline = (
            time.perf_counter() + total_timeout
            if total_timeout is not None and total_timeout > 0
            else None
        )
        lookup_timeout = self._lookup_timeout_seconds(total_timeout or 15.0)
        lat, lon, name = await self._resolve_city(
            city,
            total_timeout=lookup_timeout,
        )
        remaining = self._remaining_timeout(deadline, minimum=1.0)
        forecast = (
            await asyncio.wait_for(
                open_meteo.get_forecast(lat, lon, days),
                timeout=remaining,
            )
            if remaining is not None
            else await open_meteo.get_forecast(lat, lon, days)
        )

        lines = [f"{days}-day weather forecast for {name}:"]
        for day in forecast:
            lines.append(
                f"  {day['date']}: "
                f"{day['weather_text_en']} ({day['weather_text_zh']}), "
                f"High {day['temp_max']}°C / Low {day['temp_min']}°C"
            )
        return "\n".join(lines)
