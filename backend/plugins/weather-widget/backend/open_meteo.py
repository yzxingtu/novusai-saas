"""
Open-Meteo API 客户端

免费天气 API，无需 API Key。
- 当前天气：温度、天气代码、湿度、风速、UV 指数
- 多日预报：每日最高/最低温度、天气代码
- 地理编码：城市名搜索（支持中英文）
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("plugin.weather-widget")

# ── API 端点 ──
_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

# ── 请求超时 ──
_TIMEOUT = 10.0

# ── 内存缓存（TTL = 600s = 10 分钟）──
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 600


def _cache_get(key: str) -> Any | None:
    """获取缓存值（过期返回 None）"""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    """写入缓存"""
    _cache[key] = (time.time(), value)
    # 简单淘汰：超过 200 条清理最旧的一半
    if len(_cache) > 200:
        sorted_keys = sorted(_cache, key=lambda k: _cache[k][0])
        for k in sorted_keys[:100]:
            _cache.pop(k, None)


# ── WMO Weather Code 映射 ──
WMO_CODES: dict[int, dict[str, str]] = {
    0: {"icon": "sun", "zh": "晴", "en": "Clear sky"},
    1: {"icon": "sun", "zh": "大部晴朗", "en": "Mainly clear"},
    2: {"icon": "cloud-sun", "zh": "多云", "en": "Partly cloudy"},
    3: {"icon": "cloud", "zh": "阴天", "en": "Overcast"},
    45: {"icon": "cloud-fog", "zh": "雾", "en": "Fog"},
    48: {"icon": "cloud-fog", "zh": "雾凇", "en": "Rime fog"},
    51: {"icon": "cloud-drizzle", "zh": "小毛毛雨", "en": "Light drizzle"},
    53: {"icon": "cloud-drizzle", "zh": "毛毛雨", "en": "Moderate drizzle"},
    55: {"icon": "cloud-drizzle", "zh": "大毛毛雨", "en": "Dense drizzle"},
    56: {"icon": "cloud-drizzle", "zh": "冻毛毛雨", "en": "Light freezing drizzle"},
    57: {"icon": "cloud-drizzle", "zh": "冻雨", "en": "Dense freezing drizzle"},
    61: {"icon": "cloud-rain", "zh": "小雨", "en": "Slight rain"},
    63: {"icon": "cloud-rain", "zh": "中雨", "en": "Moderate rain"},
    65: {"icon": "cloud-rain", "zh": "大雨", "en": "Heavy rain"},
    66: {"icon": "cloud-rain", "zh": "冻雨", "en": "Light freezing rain"},
    67: {"icon": "cloud-rain", "zh": "大冻雨", "en": "Heavy freezing rain"},
    71: {"icon": "snowflake", "zh": "小雪", "en": "Slight snowfall"},
    73: {"icon": "snowflake", "zh": "中雪", "en": "Moderate snowfall"},
    75: {"icon": "snowflake", "zh": "大雪", "en": "Heavy snowfall"},
    77: {"icon": "snowflake", "zh": "雪粒", "en": "Snow grains"},
    80: {"icon": "cloud-rain", "zh": "小阵雨", "en": "Slight rain showers"},
    81: {"icon": "cloud-rain", "zh": "阵雨", "en": "Moderate rain showers"},
    82: {"icon": "cloud-rain", "zh": "大阵雨", "en": "Violent rain showers"},
    85: {"icon": "snowflake", "zh": "小阵雪", "en": "Slight snow showers"},
    86: {"icon": "snowflake", "zh": "大阵雪", "en": "Heavy snow showers"},
    95: {"icon": "cloud-lightning", "zh": "雷暴", "en": "Thunderstorm"},
    96: {"icon": "cloud-lightning", "zh": "雷暴伴小冰雹", "en": "Thunderstorm with slight hail"},
    99: {"icon": "cloud-lightning", "zh": "雷暴伴大冰雹", "en": "Thunderstorm with heavy hail"},
}

# 未知天气代码的默认值
_DEFAULT_WMO = {"icon": "cloud", "zh": "未知", "en": "Unknown"}


def get_wmo_info(code: int) -> dict[str, str]:
    """根据 WMO weather code 获取图标和描述"""
    return WMO_CODES.get(code, _DEFAULT_WMO)


# ── API 调用 ──


_NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_NOMINATIM_HEADERS = {"User-Agent": "NovusAI-WeatherPlugin/1.0"}


async def search_city(name: str, count: int = 5) -> list[dict]:
    """
    城市搜索（Nominatim / OpenStreetMap）

    使用 Nominatim 替代 Open-Meteo geocoding，中文支持完善。
    "吉首市"、"吉首"、"Jishou" 均可搜到。

    Args:
        name: 城市名（支持中英文）
        count: 返回结果数量

    Returns:
        [{"name": "吉首市", "country": "中国", "admin1": "湖南省",
          "latitude": 28.31, "longitude": 109.73}]
    """
    if not name or not name.strip():
        return []

    query = name.strip()
    cache_key = f"geo:{query}:{count}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_SEARCH_URL,
                params={
                    "q": query,
                    "format": "json",
                    "limit": count,
                    "accept-language": "zh",
                    "addressdetails": 1,
                    "featuretype": "city",
                },
                headers=_NOMINATIM_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        seen = set()
        for item in data:
            lat = item.get("lat")
            lon = item.get("lon")
            if lat is None or lon is None:
                continue

            address = item.get("address", {})
            city_name = (
                address.get("city")
                or address.get("town")
                or address.get("county")
                or item.get("display_name", "").split(",")[0]
            )
            if not city_name:
                continue

            dedup_key = f"{float(lat):.2f},{float(lon):.2f}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            results.append({
                "name": city_name,
                "country": address.get("country", ""),
                "admin1": address.get("state", ""),
                "latitude": float(lat),
                "longitude": float(lon),
            })

        _cache_set(cache_key, results)
        return results

    except httpx.TimeoutException:
        logger.warning("Nominatim search timeout for: %s", query)
        return []
    except Exception as exc:
        logger.warning("Nominatim search error for %s: %s", query, exc)
        return []


async def reverse_geocode(latitude: float, longitude: float) -> dict | None:
    """
    反向地理编码：坐标 → 城市名（Nominatim / OpenStreetMap）

    Args:
        latitude: 纬度
        longitude: 经度

    Returns:
        {"name": "吉首市", "country": "中国", "admin1": "湖南省", ...} 或 None
    """
    cache_key = f"rgeo:{latitude:.2f}:{longitude:.2f}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_REVERSE_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "json",
                    "zoom": 10,
                    "accept-language": "zh",
                },
                headers=_NOMINATIM_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

        address = data.get("address", {})
        city_name = (
            address.get("city")
            or address.get("town")
            or address.get("county")
            or address.get("state")
            or data.get("display_name", "").split(",")[0]
        )

        if city_name:
            result = {
                "name": city_name,
                "country": address.get("country", ""),
                "admin1": address.get("state", ""),
                "latitude": latitude,
                "longitude": longitude,
            }
            _cache_set(cache_key, result)
            return result
        return None

    except Exception as exc:
        logger.warning("Reverse geocoding error for %s,%s: %s", latitude, longitude, exc)
        return None


async def get_current_weather(
    latitude: float, longitude: float
) -> dict[str, Any]:
    """
    获取当前天气

    Args:
        latitude: 纬度
        longitude: 经度

    Returns:
        {
            "temperature": 22.5,
            "weather_code": 0,
            "weather_icon": "sun",
            "weather_text_zh": "晴",
            "weather_text_en": "Clear sky",
            "humidity": 68,
            "wind_speed": 15.2,
            "uv_index": 5.0,
            "is_day": True,
        }
    """
    cache_key = f"current:{latitude:.2f}:{longitude:.2f}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _BASE_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": ",".join([
                        "temperature_2m",
                        "weather_code",
                        "relative_humidity_2m",
                        "wind_speed_10m",
                        "uv_index",
                        "is_day",
                    ]),
                    "timezone": "auto",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        weather_code = current.get("weather_code", 0)
        wmo = get_wmo_info(weather_code)

        result = {
            "temperature": current.get("temperature_2m"),
            "weather_code": weather_code,
            "weather_icon": wmo["icon"],
            "weather_text_zh": wmo["zh"],
            "weather_text_en": wmo["en"],
            "humidity": current.get("relative_humidity_2m"),
            "wind_speed": current.get("wind_speed_10m"),
            "uv_index": current.get("uv_index"),
            "is_day": bool(current.get("is_day", 1)),
        }

        _cache_set(cache_key, result)
        return result

    except httpx.TimeoutException:
        logger.warning("Weather API timeout for: %s, %s", latitude, longitude)
        raise
    except Exception as exc:
        logger.warning("Weather API error: %s", exc)
        raise


async def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 3,
) -> list[dict[str, Any]]:
    """
    获取多日天气预报

    Args:
        latitude: 纬度
        longitude: 经度
        days: 预报天数（1-7）

    Returns:
        [
            {
                "date": "2026-02-23",
                "temp_max": 25.0,
                "temp_min": 15.0,
                "weather_code": 0,
                "weather_icon": "sun",
                "weather_text_zh": "晴",
                "weather_text_en": "Clear sky",
            },
            ...
        ]
    """
    days = max(1, min(days, 7))

    cache_key = f"forecast:{latitude:.2f}:{longitude:.2f}:{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                _BASE_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": ",".join([
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "weather_code",
                    ]),
                    "timezone": "auto",
                    "forecast_days": days,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        temp_max_list = daily.get("temperature_2m_max", [])
        temp_min_list = daily.get("temperature_2m_min", [])
        code_list = daily.get("weather_code", [])

        results = []
        for i, date in enumerate(dates):
            code = code_list[i] if i < len(code_list) else 0
            wmo = get_wmo_info(code)
            results.append({
                "date": date,
                "temp_max": temp_max_list[i] if i < len(temp_max_list) else None,
                "temp_min": temp_min_list[i] if i < len(temp_min_list) else None,
                "weather_code": code,
                "weather_icon": wmo["icon"],
                "weather_text_zh": wmo["zh"],
                "weather_text_en": wmo["en"],
            })

        _cache_set(cache_key, results)
        return results

    except httpx.TimeoutException:
        logger.warning("Forecast API timeout for: %s, %s", latitude, longitude)
        raise
    except Exception as exc:
        logger.warning("Forecast API error: %s", exc)
        raise
