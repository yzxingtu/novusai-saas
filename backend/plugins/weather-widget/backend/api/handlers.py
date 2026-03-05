"""
天气 API 代理路由

供前端天气组件调用，避免 CORS 问题。
走插件 API dispatcher 分发，路径:
  GET /tenant/plugins/weather-widget/api/current?lat=&lon=
  GET /tenant/plugins/weather-widget/api/forecast?lat=&lon=&days=
  GET /tenant/plugins/weather-widget/api/geocoding?name=

修复:
  - 实现 cache_ttl 缓存（进程内 dict，避免高频外部 API 调用）
  - 冷启动重试（首次失败自动重试一次，解决 500）
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger("plugin.weather-widget.api")

# ── 进程级内存缓存 ──────────────────────────────────────────────────────────
# key: (type, lat_r, lon_r, days)  value: (timestamp, data)
_cache: dict[tuple, tuple[float, Any]] = {}
_DEFAULT_TTL = 600  # 默认 10 分钟（与 config_schema default 一致）
# ────────────────────────────────────────────────────────────────────────────


def _cache_get(key: tuple, ttl: int) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < ttl:
        return entry[1]
    return None


def _cache_set(key: tuple, data: Any) -> None:
    _cache[key] = (time.time(), data)


def _get_open_meteo():
    """动态加载 open_meteo 模块（避免相对导入在 importlib 加载时失败）"""
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


async def _get_plugin_config(ctx) -> dict:
    """读取天气插件的全局配置"""
    try:
        config = await ctx.get_config()
        return config if isinstance(config, dict) else {}
    except Exception:
        return {}


async def get_config(request, ctx) -> dict:
    """
    获取天气插件配置（供前端读取）

    Returns:
        插件 config 对象（含 default_city, temperature_unit, forecast_days, cache_ttl, auto_refresh）
    """
    config = await _get_plugin_config(ctx)
    if not config.get("default_city"):
        config["default_city"] = "Shanghai"
    return {"config": config}


async def get_current_weather(request, ctx) -> dict:
    """
    获取当前天气（带 cache_ttl 缓存 + 冷启动重试）

    Query params:
        lat: 纬度 (float, 必填)
        lon: 经度 (float, 必填)
    """
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")

    if not lat or not lon:
        return {"error": "lat and lon are required", "code": 4001}

    try:
        latitude = float(lat)
        longitude = float(lon)
    except (ValueError, TypeError):
        return {"error": "lat and lon must be valid numbers", "code": 4001}

    # 读取 cache_ttl 配置（默认 600s）
    plugin_config = await _get_plugin_config(ctx)
    ttl = int(plugin_config.get("cache_ttl", _DEFAULT_TTL))

    # 检查缓存（精度取 2 位小数减少 key 碎片）
    cache_key = ("current", round(latitude, 2), round(longitude, 2))
    cached = _cache_get(cache_key, ttl)
    if cached is not None:
        return {"weather": cached}

    # 调用外部 API，首次失败自动重试一次（冷启动重试）
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            weather = await _get_open_meteo().get_current_weather(latitude, longitude)
            _cache_set(cache_key, weather)
            return {"weather": weather}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.warning("Weather API attempt 1 failed, retrying: %r", exc)

    logger.warning("Failed to get current weather after retry: %r", last_exc)
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def get_forecast(request, ctx) -> dict:
    """
    获取天气预报（带 cache_ttl 缓存 + 冷启动重试）

    Query params:
        lat: 纬度 (float, 必填)
        lon: 经度 (float, 必填)
        days: 预报天数 (int, 可选, 未指定时从插件配置读取 forecast_days)
    """
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")
    days_str = request.query_params.get("days", "")

    if not lat or not lon:
        return {"error": "lat and lon are required", "code": 4001}

    try:
        latitude = float(lat)
        longitude = float(lon)
    except (ValueError, TypeError):
        return {"error": "lat and lon must be valid numbers", "code": 4001}

    plugin_config = await _get_plugin_config(ctx)
    ttl = int(plugin_config.get("cache_ttl", _DEFAULT_TTL))

    if days_str:
        try:
            days = int(days_str)
        except (ValueError, TypeError):
            days = 3
    else:
        days = plugin_config.get("forecast_days", 3)

    cache_key = ("forecast", round(latitude, 2), round(longitude, 2), days)
    cached = _cache_get(cache_key, ttl)
    if cached is not None:
        return {"forecast": cached}

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            forecast = await _get_open_meteo().get_forecast(latitude, longitude, days)
            _cache_set(cache_key, forecast)
            return {"forecast": forecast}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.warning("Forecast API attempt 1 failed, retrying: %r", exc)

    logger.warning("Failed to get forecast after retry: %r", last_exc)
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def search_city(request, ctx) -> dict:
    """
    城市搜索 / 反向地理编码

    Query params:
        name: 城市名 (str, 支持中英文) — 与 lat/lon 二选一
        lat: 纬度 (float) — 与 name 二选一，用于反向地理编码
        lon: 经度 (float) — 与 name 二选一
        count: 返回数量 (int, 可选, 默认 5)
    """
    name = request.query_params.get("name", "")
    lat = request.query_params.get("lat", "")
    lon = request.query_params.get("lon", "")
    count_str = request.query_params.get("count", "5")

    # 反向地理编码模式：lat + lon
    if lat and lon:
        try:
            latitude = float(lat)
            longitude = float(lon)
        except (ValueError, TypeError):
            return {"error": "lat and lon must be valid numbers", "code": 4001}
        try:
            city = await _get_open_meteo().reverse_geocode(latitude, longitude)
            return {"cities": [city] if city else []}
        except Exception as exc:
            logger.warning("Failed to reverse geocode: %r", exc)
            return {"cities": []}

    # 正向搜索模式：name
    if not name.strip():
        return {"error": "name or lat/lon is required", "code": 4001}

    try:
        count = int(count_str)
    except (ValueError, TypeError):
        count = 5

    try:
        cities = await _get_open_meteo().search_city(name, count)
        return {"cities": cities}
    except Exception as exc:
        logger.warning("Failed to search city: %r", exc)
        return {"error": str(exc) or repr(exc), "code": 5000}
