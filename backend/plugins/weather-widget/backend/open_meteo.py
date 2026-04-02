"""
Open-Meteo API 客户端

免费天气 API，无需 API Key。
- 合并请求：一次获取 current + daily + hourly 全量数据
- 空气质量：独立 API 获取 AQI / PM2.5 / PM10
- 地理编码：Nominatim（含 rate-limit）+ Open-Meteo 二次反查
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("plugin.weather-widget")


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

# ── API 端点 / API endpoints ──
_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

_NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_NOMINATIM_HEADERS = {"User-Agent": "NovusAI-WeatherPlugin/1.0"}

# ── 超时 / timeouts ──
_WEATHER_TIMEOUT = 10.0
_NOMINATIM_TIMEOUT = 5.0

# ── Nominatim Rate-Limit (1 req/s) / Nominatim 限速 1 次每秒 ──
_nominatim_lock = asyncio.Lock()
_nominatim_last_ts: float = 0.0


async def _nominatim_throttle() -> None:
    """Enforce 1 request/second for Nominatim (OSM usage policy). / 说明"""
    global _nominatim_last_ts
    async with _nominatim_lock:
        now = time.monotonic()
        gap = 1.0 - (now - _nominatim_last_ts)
        if gap > 0:
            await asyncio.sleep(gap)
        _nominatim_last_ts = time.monotonic()


def _make_client(timeout: float = _WEATHER_TIMEOUT) -> httpx.AsyncClient:
    # Keep TLS verification enabled by default for all outbound weather requests.
    transport = httpx.AsyncHTTPTransport(verify=True)
    return httpx.AsyncClient(timeout=timeout, transport=transport)


# ── 内存缓存 (TTL = 600s) ──
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 600

_CITY_QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "北京": ("北京市", "Beijing"),
    "北京市": ("北京", "Beijing"),
    "beijing": ("北京市", "北京"),
    "上海": ("上海市", "Shanghai"),
    "上海市": ("上海", "Shanghai"),
    "shanghai": ("上海市", "上海"),
    "天津": ("天津市", "Tianjin"),
    "天津市": ("天津", "Tianjin"),
    "tianjin": ("天津市", "天津"),
    "重庆": ("重庆市", "Chongqing"),
    "重庆市": ("重庆", "Chongqing"),
    "chongqing": ("重庆市", "重庆"),
}

_CITY_SUFFIXES = ("市", "区", "县", "州", "省", "自治区", "特别行政区")


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)
    if len(_cache) > 200:
        sorted_keys = sorted(_cache, key=lambda k: _cache[k][0])
        for k in sorted_keys[:100]:
            _cache.pop(k, None)


def _merge_city_results(
    results: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    merged = list(results)
    seen = {
        (
            round(float(item.get("latitude", 0.0)), 2),
            round(float(item.get("longitude", 0.0)), 2),
        )
        for item in merged
    }
    for item in incoming:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if lat is None or lon is None:
            continue
        dedup_key = (round(float(lat), 2), round(float(lon), 2))
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged[:limit]


def _expand_city_queries(name: str) -> list[str]:
    query = (name or "").strip()
    if not query:
        return []

    expanded: list[str] = [query]
    lowered = query.lower()
    for alias in _CITY_QUERY_ALIASES.get(lowered, ()) + _CITY_QUERY_ALIASES.get(query, ()):
        text = str(alias or "").strip()
        if text and text not in expanded:
            expanded.append(text)

    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in query)
    if has_cjk and not query.endswith(_CITY_SUFFIXES):
        with_suffix = f"{query}市"
        if with_suffix not in expanded:
            expanded.append(with_suffix)

    if query.endswith("市"):
        without_suffix = query[:-1].strip()
        if without_suffix and without_suffix not in expanded:
            expanded.append(without_suffix)

    return expanded


def _normalize_city_label(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace(" ", "")
    if text.endswith("市"):
        return text[:-1]
    return text


def _rank_city_candidate(
    *,
    original_query: str,
    expanded_queries: list[str],
    candidate: dict[str, Any],
) -> tuple[int, str]:
    query_norm = _normalize_city_label(original_query)
    expanded_norms = {_normalize_city_label(item) for item in expanded_queries if item}

    name = str(candidate.get("name") or "").strip()
    admin1 = str(candidate.get("admin1") or "").strip()
    country = str(candidate.get("country") or "").strip()
    name_norm = _normalize_city_label(name)
    admin1_norm = _normalize_city_label(admin1)

    score = 0
    if name_norm == query_norm:
        score += 12
    if name in expanded_queries:
        score += 8
    if name_norm in expanded_norms:
        score += 10
    if admin1_norm == query_norm:
        score += 8
    if admin1 in expanded_queries:
        score += 6
    if admin1_norm in expanded_norms:
        score += 6
    if query_norm and query_norm in name_norm:
        score += 4
    if query_norm and query_norm in admin1_norm:
        score += 3
    if name.endswith("市"):
        score += 5
    if country in {"中国", "China"}:
        score += 1

    return (score, name)


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

_DEFAULT_WMO = {"icon": "cloud", "zh": "未知", "en": "Unknown"}


def get_wmo_info(code: int) -> dict[str, str]:
    return WMO_CODES.get(code, _DEFAULT_WMO)


# ── 合并天气请求 (current + daily + hourly) ──


async def get_weather_all(
    latitude: float,
    longitude: float,
    days: int = 3,
) -> dict[str, Any]:
    """单次请求获取 current + daily + hourly 全量天气数据 / Single request for current + daily + hourly weather.

    Returns:
        {
            "current": { temperature, apparent_temperature, weather_code, humidity,
                         wind_speed, uv_index, is_day, weather_icon, weather_text_zh/en },
            "daily": [{ date, temp_max, temp_min, weather_code, sunrise, sunset, ... }],
            "hourly": [{ time, temperature, weather_code, weather_icon, weather_text_zh/en }],
        }
    """
    days = max(1, min(days, 7))
    cache_key = f"all:{latitude:.2f}:{longitude:.2f}:{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    async with _make_client() as client:
        resp = await client.get(
            _BASE_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": ",".join([
                    "temperature_2m",
                    "apparent_temperature",
                    "weather_code",
                    "relative_humidity_2m",
                    "wind_speed_10m",
                    "uv_index",
                    "is_day",
                ]),
                "daily": ",".join([
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "weather_code",
                    "sunrise",
                    "sunset",
                ]),
                "hourly": "temperature_2m,weather_code",
                "timezone": "auto",
                "forecast_days": days,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    # parse current / 解析当前天气块
    cur = data.get("current", {})
    wcode = cur.get("weather_code", 0)
    wmo = get_wmo_info(wcode)
    current_out = {
        "temperature": cur.get("temperature_2m"),
        "apparent_temperature": cur.get("apparent_temperature"),
        "weather_code": wcode,
        "weather_icon": wmo["icon"],
        "weather_text_zh": wmo["zh"],
        "weather_text_en": wmo["en"],
        "humidity": cur.get("relative_humidity_2m"),
        "wind_speed": cur.get("wind_speed_10m"),
        "uv_index": cur.get("uv_index"),
        "is_day": bool(cur.get("is_day", 1)),
    }

    # parse daily / 解析逐日预报
    daily_raw = data.get("daily", {})
    dates = daily_raw.get("time", [])
    daily_out = []
    for i, date in enumerate(dates):
        code = (daily_raw.get("weather_code") or [])[i] if i < len(daily_raw.get("weather_code", [])) else 0
        w = get_wmo_info(code)
        sunrises = daily_raw.get("sunrise", [])
        sunsets = daily_raw.get("sunset", [])
        daily_out.append({
            "date": date,
            "temp_max": (daily_raw.get("temperature_2m_max") or [])[i] if i < len(daily_raw.get("temperature_2m_max", [])) else None,
            "temp_min": (daily_raw.get("temperature_2m_min") or [])[i] if i < len(daily_raw.get("temperature_2m_min", [])) else None,
            "weather_code": code,
            "weather_icon": w["icon"],
            "weather_text_zh": w["zh"],
            "weather_text_en": w["en"],
            "sunrise": sunrises[i] if i < len(sunrises) else None,
            "sunset": sunsets[i] if i < len(sunsets) else None,
        })

    # parse hourly (next 24 hours from now) / 解析逐小时（自当前起 24 小时）
    hourly_raw = data.get("hourly", {})
    h_times = hourly_raw.get("time", [])
    h_temps = hourly_raw.get("temperature_2m", [])
    h_codes = hourly_raw.get("weather_code", [])

    now_iso = cur.get("time", "")
    now_hour = now_iso[:13] if len(now_iso) >= 13 else ""
    start_idx = 0
    for idx, t in enumerate(h_times):
        if t[:13] >= now_hour:
            start_idx = idx
            break

    hourly_out = []
    for j in range(start_idx, min(start_idx + 24, len(h_times))):
        hcode = h_codes[j] if j < len(h_codes) else 0
        hw = get_wmo_info(hcode)
        raw_time = h_times[j]
        display_time = raw_time[11:16] if len(raw_time) >= 16 else raw_time
        hourly_out.append({
            "time": display_time,
            "temperature": h_temps[j] if j < len(h_temps) else None,
            "weather_code": hcode,
            "weather_icon": hw["icon"],
            "weather_text_zh": hw["zh"],
            "weather_text_en": hw["en"],
            "is_current": j == start_idx,
        })

    result = {
        "current": current_out,
        "daily": daily_out,
        "hourly": hourly_out,
    }
    _cache_set(cache_key, result)
    return result


# ── 保留向后兼容的单独接口 (内部复用 get_weather_all) ──


async def get_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
    all_data = await get_weather_all(latitude, longitude)
    return all_data["current"]


async def get_forecast(latitude: float, longitude: float, days: int = 3) -> list[dict[str, Any]]:
    all_data = await get_weather_all(latitude, longitude, days)
    return all_data["daily"]


# ── 空气质量 / air quality ──


async def get_air_quality(latitude: float, longitude: float) -> dict[str, Any]:
    """获取空气质量数据 (Open-Meteo Air Quality API) / Get air quality (Open-Meteo Air Quality API).

    Returns:
        {
            "aqi": 42,       — US AQI（美标指数）
            "pm2_5": 12.3,
            "pm10": 25.1,
            "european_aqi": 35,
        }
    """
    cache_key = f"aqi:{latitude:.2f}:{longitude:.2f}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        async with _make_client() as client:
            resp = await client.get(
                _AQI_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "us_aqi,pm2_5,pm10,european_aqi",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        current = data.get("current", {})
        result = {
            "aqi": current.get("us_aqi"),
            "pm2_5": current.get("pm2_5"),
            "pm10": current.get("pm10"),
            "european_aqi": current.get("european_aqi"),
        }
        _cache_set(cache_key, result)
        return result

    except Exception as exc:
        logger.warning("Air quality API error: {}", _describe_exception(exc))
        return {"aqi": None, "pm2_5": None, "pm10": None, "european_aqi": None}


# ── 城市搜索 (Nominatim) ──


async def search_city(name: str, count: int = 5) -> list[dict]:
    if not name or not name.strip():
        return []

    query = name.strip()
    cache_key = f"geo:{query}:{count}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    queries = _expand_city_queries(query)
    merged_results: list[dict[str, Any]] = []
    try:
        for candidate in queries[:1]:
            results = await _search_city_nominatim(candidate, count)
            merged_results = _merge_city_results(merged_results, results, limit=count)

        for candidate in queries:
            results = await _search_city_open_meteo(candidate, count)
            merged_results = _merge_city_results(
                merged_results,
                results,
                limit=max(count * 4, count),
            )

        merged_results = sorted(
            merged_results,
            key=lambda item: _rank_city_candidate(
                original_query=query,
                expanded_queries=queries,
                candidate=item,
            ),
            reverse=True,
        )[:count]

        _cache_set(cache_key, merged_results)
        return merged_results
    except Exception as exc:
        logger.warning(
            "City search error for query='{}': {}",
            query,
            _describe_exception(exc),
        )
        return merged_results


async def _search_city_nominatim(name: str, count: int) -> list[dict[str, Any]]:
    try:
        await _nominatim_throttle()
        async with _make_client(timeout=_NOMINATIM_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_SEARCH_URL,
                params={
                    "q": name,
                    "format": "json",
                    "limit": count,
                    "accept-language": "zh",
                    "addressdetails": 1,
                },
                headers=_NOMINATIM_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("Nominatim search timeout for query='{}'", name)
        return []
    except Exception as exc:
        logger.warning(
            "Nominatim search error for query='{}': {}",
            name,
            _describe_exception(exc),
        )
        return []

    results = []
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
            or address.get("state")
            or item.get("display_name", "").split(",")[0]
        )
        if not city_name:
            continue

        results.append(
            {
                "name": city_name,
                "country": address.get("country", ""),
                "admin1": address.get("state", ""),
                "latitude": float(lat),
                "longitude": float(lon),
            }
        )
    return results[:count]


async def _search_city_open_meteo(name: str, count: int) -> list[dict[str, Any]]:
    try:
        async with _make_client() as client:
            resp = await client.get(
                _GEOCODING_URL,
                params={
                    "name": name,
                    "count": count,
                    "language": "zh",
                    "format": "json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "Open-Meteo geocoding search error for query='{}': {}",
            name,
            _describe_exception(exc),
        )
        return []

    results = []
    for item in data.get("results", []) or []:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if lat is None or lon is None:
            continue
        city_name = str(item.get("name") or "").strip()
        if not city_name:
            continue
        results.append(
            {
                "name": city_name,
                "country": item.get("country", ""),
                "admin1": item.get("admin1", ""),
                "latitude": float(lat),
                "longitude": float(lon),
            }
        )
    return results[:count]


# ── 反向地理编码 / reverse geocoding ──

_CITY_FIELDS = ("city", "town", "village", "county", "suburb", "state_district", "state")


async def reverse_geocode(latitude: float, longitude: float) -> dict | None:
    """坐标 -> 城市名。优先 Nominatim zoom=14，失败回退 Open-Meteo geocoding / Coords to city name (Nominatim then Open-Meteo fallback)."""
    cache_key = f"rgeo:{latitude:.2f}:{longitude:.2f}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 1) Nominatim reverse (zoom=14 for better city-level accuracy) / Nominatim 反向，zoom=14 提高城市精度
    result = await _reverse_nominatim(latitude, longitude)
    if result:
        _cache_set(cache_key, result)
        return result

    # 2) Fallback: Open-Meteo geocoding nearest match / 回退 Open-Meteo 最近城市匹配
    result = await _reverse_open_meteo(latitude, longitude)
    if result:
        _cache_set(cache_key, result)
        return result

    return None


async def _reverse_nominatim(latitude: float, longitude: float) -> dict | None:
    try:
        await _nominatim_throttle()
        async with _make_client(timeout=_NOMINATIM_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_REVERSE_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "json",
                    "zoom": 14,
                    "accept-language": "zh",
                },
                headers=_NOMINATIM_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()

        address = data.get("address", {})
        city_name = None
        for field in _CITY_FIELDS:
            if address.get(field):
                city_name = address[field]
                break

        if not city_name:
            display = data.get("display_name", "")
            if display:
                city_name = display.split(",")[0].strip()

        if city_name:
            return {
                "name": city_name,
                "country": address.get("country", ""),
                "admin1": address.get("state", ""),
                "latitude": latitude,
                "longitude": longitude,
            }
        return None

    except Exception as exc:
        logger.warning(
            "Nominatim reverse error for lat={} lon={}: {}",
            latitude,
            longitude,
            _describe_exception(exc),
        )
        return None


async def _reverse_open_meteo(latitude: float, longitude: float) -> dict | None:
    """Fallback: use Open-Meteo geocoding API to find nearest city. / 接口/处理器"""
    try:
        async with _make_client() as client:
            resp = await client.get(
                _GEOCODING_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "count": 1,
                    "language": "zh",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results", [])
        if results:
            r = results[0]
            return {
                "name": r.get("name", ""),
                "country": r.get("country", ""),
                "admin1": r.get("admin1", ""),
                "latitude": r.get("latitude", latitude),
                "longitude": r.get("longitude", longitude),
            }
        return None

    except Exception as exc:
        logger.warning(
            "Open-Meteo geocoding fallback error for lat={} lon={}: {}",
            latitude,
            longitude,
            _describe_exception(exc),
        )
        return None
