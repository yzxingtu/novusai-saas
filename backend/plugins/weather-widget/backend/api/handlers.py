"""天气 API 路由 / Weather API routes.

供前端天气组件调用，避免 CORS；缓存由天气插件 provider 管理。
路由: GET /current, /forecast, /hourly, /air-quality, /geocoding, /config
"""

from __future__ import annotations

from app.core.i18n import _
from app.core.logging import get_logger

logger = get_logger("plugin.weather-widget.api")


def _describe_exception(exc: Exception | None) -> str:
    """Build a readable exception summary for Loguru-based logs / 为 Loguru 日志构造可读异常摘要。"""
    if exc is None:
        return "unknown error"

    parts: list[str] = []
    current: Exception | BaseException | None = exc
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        text = str(current).strip()
        if text:
            parts.append(f"{type(current).__name__}: {text}")
        else:
            parts.append(repr(current))
        current = current.__cause__ or current.__context__

    return " <- ".join(parts)


def _get_open_meteo():
    from app.plugins.module_loader import load_plugin_module

    provider = load_plugin_module("weather-widget", "open_meteo")
    if provider is None:
        raise ImportError("Cannot load weather-widget.open_meteo")
    return provider


def _parse_coords(request) -> tuple[float, float] | dict:
    """从查询参数解析并校验 lat/lon，返回 (lat, lon) 或错误 dict / Extract and validate lat/lon from query params. Returns (lat, lon) or error dict."""
    lat = request.query_params.get("lat")
    lon = request.query_params.get("lon")
    if not lat or not lon:
        return {
            "error": _("plugin.weather-widget.error.lat_lon_required"),
            "code": 4001,
        }
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


def _sanitize_public_config(config: dict) -> dict:
    public_config = dict(config)
    public_config.pop("qweather_api_host", None)
    public_config.pop("qweather_api_key", None)
    public_config.pop("api_host", None)
    public_config.pop("api_key", None)
    return public_config


def _configure_provider(provider, config: dict) -> None:
    configure = getattr(provider, "configure", None)
    if callable(configure):
        configure(config)


def _parse_forecast_days(request, provider, plugin_config: dict) -> int | dict:
    """中文: 校验 forecast days，非法输入返回公开错误。

    EN: Validate forecast days and return a public error for invalid input.
    """
    validator = getattr(provider, "validate_forecast_days", None)
    if not callable(validator):
        raise ImportError("Weather provider is missing validate_forecast_days")

    days_value = request.query_params.get("days")
    try:
        if days_value is None:
            return validator(None, default=plugin_config.get("forecast_days", 3))
        return validator(days_value)
    except ValueError:
        return {
            "error": _("plugin.weather-widget.error.days_invalid"),
            "code": 4001,
        }


# ── 路由 / routes ──


async def get_config(request, ctx) -> dict:
    _request = request
    config = _sanitize_public_config(await _get_plugin_config(ctx))
    if not config.get("default_city"):
        config["default_city"] = "Shanghai"
    return {"config": config}


async def get_current_weather(request, ctx) -> dict:
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    plugin_config = await _get_plugin_config(ctx)
    provider = _get_open_meteo()
    _configure_provider(provider, plugin_config)

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            all_data = await provider.get_weather_all(latitude, longitude)
            return {"weather": all_data["current"]}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.info(
                    "Weather API attempt {} failed for lat={} lon={}: {}",
                    attempt + 1,
                    latitude,
                    longitude,
                    _describe_exception(exc),
                )

    logger.warning(
        "Failed to get current weather after retry for lat={} lon={}: {}",
        latitude,
        longitude,
        _describe_exception(last_exc),
    )
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def get_forecast(request, ctx) -> dict:
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    plugin_config = await _get_plugin_config(ctx)
    provider = _get_open_meteo()
    _configure_provider(provider, plugin_config)
    days = _parse_forecast_days(request, provider, plugin_config)
    if isinstance(days, dict):
        return days

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            all_data = await provider.get_weather_all(latitude, longitude, days)
            return {"forecast": all_data["daily"]}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.info(
                    "Forecast API attempt {} failed for lat={} lon={} days={}: {}",
                    attempt + 1,
                    latitude,
                    longitude,
                    days,
                    _describe_exception(exc),
                )

    logger.warning(
        "Failed to get forecast after retry for lat={} lon={} days={}: {}",
        latitude,
        longitude,
        days,
        _describe_exception(last_exc),
    )
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def get_hourly(request, ctx) -> dict:
    """返回未来 24h 逐小时天气。 / Return next 24h hourly weather."""
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    plugin_config = await _get_plugin_config(ctx)
    provider = _get_open_meteo()
    _configure_provider(provider, plugin_config)

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            all_data = await provider.get_weather_all(latitude, longitude)
            return {"hourly": all_data["hourly"]}
        except Exception as exc:
            last_exc = exc
            if attempt == 0:
                logger.info(
                    "Hourly API attempt {} failed for lat={} lon={}: {}",
                    attempt + 1,
                    latitude,
                    longitude,
                    _describe_exception(exc),
                )

    logger.warning(
        "Failed to get hourly after retry for lat={} lon={}: {}",
        latitude,
        longitude,
        _describe_exception(last_exc),
    )
    return {"error": str(last_exc) or repr(last_exc), "code": 5000}


async def get_air_quality(request, ctx) -> dict:
    """返回 AQI 空气质量数据。 / Return AQI air quality data."""
    coords = _parse_coords(request)
    if isinstance(coords, dict):
        return coords
    latitude, longitude = coords

    provider = _get_open_meteo()
    _configure_provider(provider, await _get_plugin_config(ctx))

    try:
        aqi = await provider.get_air_quality(latitude, longitude)
        return {"air_quality": aqi}
    except Exception as exc:
        logger.warning(
            "AQI API error for lat={} lon={}: {}",
            latitude,
            longitude,
            _describe_exception(exc),
        )
        return {
            "air_quality": {
                "aqi": None,
                "pm2_5": None,
                "pm10": None,
                "european_aqi": None,
            }
        }


async def search_city(request, ctx) -> dict:
    name = request.query_params.get("name", "")
    lat = request.query_params.get("lat", "")
    lon = request.query_params.get("lon", "")
    count_str = request.query_params.get("count", "5")

    provider = _get_open_meteo()
    _configure_provider(provider, await _get_plugin_config(ctx))

    if lat and lon:
        try:
            latitude = float(lat)
            longitude = float(lon)
        except (ValueError, TypeError):
            return {
                "error": _("plugin.weather-widget.error.lat_lon_invalid"),
                "code": 4001,
            }
        try:
            city = await provider.reverse_geocode(latitude, longitude)
            return {"cities": [city] if city else []}
        except Exception as exc:
            logger.warning(
                "Failed to reverse geocode for lat={} lon={}: {}",
                latitude,
                longitude,
                _describe_exception(exc),
            )
            return {"cities": []}

    if not name.strip():
        return {
            "error": _("plugin.weather-widget.error.name_or_coords_required"),
            "code": 4001,
        }

    try:
        count = int(count_str)
    except (ValueError, TypeError):
        count = 5

    try:
        cities = await provider.search_city(name, count)
        return {"cities": cities}
    except Exception as exc:
        logger.warning(
            "Failed to look up city query='{}' count={}: {}",
            name,
            count,
            _describe_exception(exc),
        )
        return {"error": str(exc) or repr(exc), "code": 5000}
