"""天气 API 路由 / Weather API routes — 供前端天气组件调用，避免 CORS；缓存由 open_meteo 管理。路由: GET /current, /forecast, /hourly, /air-quality, /geocoding, /config"""

from __future__ import annotations

from app.core.i18n import _
from app.core.logging import get_logger

logger = get_logger("plugin.weather-widget.api")


def _get_open_meteo():
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


def _parse_coords(request) -> tuple[float, float] | dict:
    """从查询参数解析并校验 lat/lon，返回 (lat, lon) 或错误 dict / Extract and validate lat/lon from query params. Returns (lat, lon) or error dict."""
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")
    if not lat or not lon:
        return {"error": _("plugin.weather-widget.error.lat_lon_required"), "code": 4001}
    try:
        return float(lat), float(lon)
    except (ValueError, TypeError):
        return {"error": _("plugin.weather-widget.error.lat_lon_invalid"), "code": 4001}


async def _get_plugin_config(ctx) -> dict:
    try:
        config = await ctx.get_config()
        return config if isinstance(config, dict) else {}
    except Exception:
        return {}


# ── 路由 ──


async def get_config(request, ctx) -> dict:
    config = await _get_plugin_config(ctx)
    if not config.get("default_city"):
        config["default_city"] = "Shanghai"
    return {"config": config}


async def get_current_weather(request, ctx) -> dict:
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            all_data = await _get_open_meteo().get_weather_all(latitude, longitude)
            return {"weather": all_data["current"]}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.warning("Weather API attempt 1 failed, retrying: %r", exc)

    logger.warning("Failed to get current weather after retry: %r", last_exc)
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def get_forecast(request, ctx) -> dict:
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    plugin_config = await _get_plugin_config(ctx)
    days_str = request.query_params.get("days", "")
    if days_str:
        try:
            days = int(days_str)
        except (ValueError, TypeError):
            days = 3
    else:
        days = plugin_config.get("forecast_days", 3)

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            all_data = await _get_open_meteo().get_weather_all(latitude, longitude, days)
            return {"forecast": all_data["daily"]}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.warning("Forecast API attempt 1 failed, retrying: %r", exc)

    logger.warning("Failed to get forecast after retry: %r", last_exc)
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def get_hourly(request, ctx) -> dict:
    """返回未来 24h 逐小时天气。 / Return next 24h hourly weather."""
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            all_data = await _get_open_meteo().get_weather_all(latitude, longitude)
            return {"hourly": all_data["hourly"]}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.warning("Hourly API attempt 1 failed, retrying: %r", exc)

    logger.warning("Failed to get hourly after retry: %r", last_exc)
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def get_air_quality(request, ctx) -> dict:
    """返回 AQI 空气质量数据。 / Return AQI air quality data."""
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    try:
        aqi = await _get_open_meteo().get_air_quality(latitude, longitude)
        return {"air_quality": aqi}
    except Exception as exc:
        logger.warning("AQI API error: %r", exc)
        return {"air_quality": {"aqi": None, "pm2_5": None, "pm10": None, "european_aqi": None}}


async def search_city(request, ctx) -> dict:
    name = request.query_params.get("name", "")
    lat = request.query_params.get("lat", "")
    lon = request.query_params.get("lon", "")
    count_str = request.query_params.get("count", "5")

    if lat and lon:
        try:
            latitude = float(lat)
            longitude = float(lon)
        except (ValueError, TypeError):
            return {"error": _("plugin.weather-widget.error.lat_lon_invalid"), "code": 4001}
        try:
            city = await _get_open_meteo().reverse_geocode(latitude, longitude)
            return {"cities": [city] if city else []}
        except Exception as exc:
            logger.warning("Failed to reverse geocode: %r", exc)
            return {"cities": []}

    if not name.strip():
        return {"error": _("plugin.weather-widget.error.name_or_coords_required"), "code": 4001}

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
