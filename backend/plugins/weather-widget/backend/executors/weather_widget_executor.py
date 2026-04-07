"""实时天气工具执行器 / Description.

调用 Open-Meteo API 获取真实天气数据，支持当前天气和多日预报两个工具。"""

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
    """Load open_meteo module via shared loader / 通过共享加载器加载 open_meteo"""
    import importlib.util
    import sys
    from pathlib import Path

    loader_name = "plugins.weather-widget.backend._loader"
    if loader_name not in sys.modules:
        loader_file = Path(__file__).parent.parent / "_loader.py"
        spec = importlib.util.spec_from_file_location(loader_name, loader_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {loader_file}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[loader_name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[loader_name].get_open_meteo()


class WeatherWidgetExecutor(BaseToolExecutor):
    """实时天气执行器（调用 Open-Meteo API） / Realtime weather executor (Open-Meteo API)."""

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
    def _remaining_timeout(deadline: float | None, *, minimum: float = 0.5) -> float | None:
        if deadline is None:
            return None
        remaining = deadline - time.perf_counter()
        if remaining <= minimum:
            return None
        return remaining

    @staticmethod
    def _lookup_candidates(city: str, open_meteo: Any) -> list[str]:
        candidates = [city]
        trim = (
            open_meteo.__dict__.get("_trim_city_label_suffix")
            if hasattr(open_meteo, "__dict__")
            else getattr(open_meteo, "_trim_city_label_suffix", None)
        )
        if callable(trim):
            trimmed = str(trim(city) or "").strip()
            if trimmed and trimmed not in candidates:
                candidates.append(trimmed)
        return candidates

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

        try:
            if tool_name == "get_current_weather":
                output = await self._get_current(city, total_timeout=tool_timeout)
            elif tool_name == "get_weather_forecast":
                days = arguments.get("days", 3)
                if not isinstance(days, int):
                    try:
                        days = int(days)
                    except (ValueError, TypeError):
                        days = 3
                output = await self._get_forecast(
                    city,
                    days,
                    total_timeout=tool_timeout,
                )
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
        queries = self._lookup_candidates(city, open_meteo)
        direct_open_meteo_search = (
            open_meteo.__dict__.get("_search_city_open_meteo")
            if hasattr(open_meteo, "__dict__")
            else getattr(open_meteo, "_search_city_open_meteo", None)
        )
        attempted_timeout = False

        lookup_steps: list[tuple[str, str]] = [("smart", queries[0])]
        if len(queries) > 1:
            lookup_steps.append(("direct", queries[1]))

        for mode, query in lookup_steps:
            remaining = self._remaining_timeout(deadline)
            if remaining is None:
                break
            step_timeout = remaining
            if (
                mode == "smart"
                and len(lookup_steps) > 1
                and total_timeout is not None
                and total_timeout > 0
            ):
                step_timeout = min(
                    remaining,
                    max(1.0, total_timeout * 0.6),
                )
            try:
                if mode == "direct" and callable(direct_open_meteo_search):
                    results = await asyncio.wait_for(
                        direct_open_meteo_search(query, 1),
                        timeout=step_timeout,
                    )
                else:
                    results = await asyncio.wait_for(
                        open_meteo.search_city(query, count=1),
                        timeout=step_timeout,
                    )
            except asyncio.TimeoutError:
                attempted_timeout = True
                continue

            if not results:
                continue

            hit = results[0]
            resolved_name = hit.get("name", city)
            return hit["latitude"], hit["longitude"], resolved_name

        if attempted_timeout:
            timeout_value = max(1, int(total_timeout or 1))
            raise TimeoutError(
                _("tool.error.execution_timeout", timeout=timeout_value)
            )

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
