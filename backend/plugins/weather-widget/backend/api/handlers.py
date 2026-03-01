"""
天气 API 代理路由

供前端天气组件调用，避免 CORS 问题。
走插件 API dispatcher 分发，路径:
  GET /tenant/plugins/weather-widget/api/current?lat=&lon=
  GET /tenant/plugins/weather-widget/api/forecast?lat=&lon=&days=
  GET /tenant/plugins/weather-widget/api/geocoding?name=
"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("plugin.weather-widget.api")


from .. import open_meteo


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
    return {"config": config}


async def get_current_weather(request, ctx) -> dict:
    """
    获取当前天气

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

    try:
        weather = await open_meteo.get_current_weather(latitude, longitude)
        return {"weather": weather}
    except Exception as exc:
        logger.warning("Failed to get current weather: %s", exc)
        return {"error": str(exc), "code": 5000}


async def get_forecast(request, ctx) -> dict:
    """
    获取天气预报

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

    if days_str:
        try:
            days = int(days_str)
        except (ValueError, TypeError):
            days = 3
    else:
        plugin_config = await _get_plugin_config(ctx)
        days = plugin_config.get("forecast_days", 3)

    try:
        forecast = await open_meteo.get_forecast(latitude, longitude, days)
        return {"forecast": forecast}
    except Exception as exc:
        logger.warning("Failed to get forecast: %s", exc)
        return {"error": str(exc), "code": 5000}


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
            city = await open_meteo.reverse_geocode(latitude, longitude)
            return {"cities": [city] if city else []}
        except Exception as exc:
            logger.warning("Failed to reverse geocode: %s", exc)
            return {"cities": []}

    # 正向搜索模式：name
    if not name.strip():
        return {"error": "name or lat/lon is required", "code": 4001}

    try:
        count = int(count_str)
    except (ValueError, TypeError):
        count = 5

    try:
        cities = await open_meteo.search_city(name, count)
        return {"cities": cities}
    except Exception as exc:
        logger.warning("Failed to search city: %s", exc)
        return {"error": str(exc), "code": 5000}
