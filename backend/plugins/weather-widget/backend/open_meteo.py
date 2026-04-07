"""
MET Norway + Nominatim weather client.

The historical module name is retained for compatibility with the existing
plugin loader and executor import path.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger("plugin.weather-widget")


def _describe_exception(exc: Exception | None) -> str:
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


_MET_FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
_NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_REQUEST_HEADERS = {
    "User-Agent": "NovusAI-WeatherPlugin/1.0",
    "Accept": "application/json",
}

_WEATHER_TIMEOUT = 6.0
_GEOCODING_TIMEOUT = 4.0
_NOMINATIM_TIMEOUT = 4.0
_CITY_LOOKUP_TOTAL_TIMEOUT = 8.0

_DEFAULT_CACHE_TTL = 600
_CACHE_TTL = _DEFAULT_CACHE_TTL
_cache: dict[str, tuple[float, Any]] = {}

_nominatim_lock = asyncio.Lock()
_nominatim_last_ts: float = 0.0

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
_CITY_LABEL_TRIM_SUFFIXES = (
    "特别行政区",
    "自治州",
    "自治区",
    "自治县",
    "省",
    "市",
    "县",
)

_SYMBOL_TRANSLATIONS: dict[str, tuple[str, str]] = {
    "clearsky": ("晴", "Clear sky"),
    "fair": ("大部晴朗", "Fair"),
    "partlycloudy": ("多云", "Partly cloudy"),
    "cloudy": ("阴天", "Cloudy"),
    "fog": ("雾", "Fog"),
    "lightrain": ("小雨", "Light rain"),
    "rain": ("中雨", "Rain"),
    "heavyrain": ("大雨", "Heavy rain"),
    "lightsleet": ("小雨夹雪", "Light sleet"),
    "sleet": ("雨夹雪", "Sleet"),
    "heavysleet": ("大雨夹雪", "Heavy sleet"),
    "lightsnow": ("小雪", "Light snow"),
    "snow": ("中雪", "Snow"),
    "heavysnow": ("大雪", "Heavy snow"),
    "rainshowers": ("阵雨", "Rain showers"),
    "heavyrainshowers": ("强阵雨", "Heavy rain showers"),
    "lightrainshowers": ("小阵雨", "Light rain showers"),
    "sleetshowers": ("雨夹雪阵雨", "Sleet showers"),
    "snowshowers": ("阵雪", "Snow showers"),
    "heavysnowshowers": ("强阵雪", "Heavy snow showers"),
    "thunder": ("雷暴", "Thunderstorm"),
    "rainandthunder": ("雷阵雨", "Rain and thunder"),
    "heavyrainandthunder": ("强雷阵雨", "Heavy rain and thunder"),
    "sleetandthunder": ("雷阵雨夹雪", "Sleet and thunder"),
    "snowandthunder": ("雷阵雪", "Snow and thunder"),
    "rainshowersandthunder": ("雷阵雨", "Rain showers and thunder"),
    "sleetshowersandthunder": ("雷阵雨夹雪", "Sleet showers and thunder"),
    "snowshowersandthunder": ("雷阵雪", "Snow showers and thunder"),
}

WMO_CODES: dict[int, dict[str, str]] = {
    0: {"icon": "sun", "zh": "晴", "en": "Clear sky"},
    1: {"icon": "sun", "zh": "大部晴朗", "en": "Mainly clear"},
    2: {"icon": "cloud-sun", "zh": "多云", "en": "Partly cloudy"},
    3: {"icon": "cloud", "zh": "阴天", "en": "Overcast"},
    45: {"icon": "cloud-fog", "zh": "雾", "en": "Fog"},
    48: {"icon": "cloud-fog", "zh": "霾", "en": "Haze"},
    51: {"icon": "cloud-drizzle", "zh": "毛毛雨", "en": "Drizzle"},
    61: {"icon": "cloud-rain", "zh": "小雨", "en": "Slight rain"},
    63: {"icon": "cloud-rain", "zh": "中雨", "en": "Moderate rain"},
    65: {"icon": "cloud-rain", "zh": "大雨", "en": "Heavy rain"},
    71: {"icon": "snowflake", "zh": "小雪", "en": "Slight snowfall"},
    73: {"icon": "snowflake", "zh": "中雪", "en": "Moderate snowfall"},
    75: {"icon": "snowflake", "zh": "大雪", "en": "Heavy snowfall"},
    77: {"icon": "snowflake", "zh": "雨夹雪", "en": "Sleet"},
    80: {"icon": "cloud-rain", "zh": "小阵雨", "en": "Slight rain showers"},
    81: {"icon": "cloud-rain", "zh": "阵雨", "en": "Moderate rain showers"},
    82: {"icon": "cloud-rain", "zh": "强阵雨", "en": "Violent rain showers"},
    85: {"icon": "snowflake", "zh": "阵雪", "en": "Snow showers"},
    95: {"icon": "cloud-lightning", "zh": "雷暴", "en": "Thunderstorm"},
    96: {"icon": "cloud-lightning", "zh": "强雷暴", "en": "Strong thunderstorm"},
}

_DEFAULT_WMO = {"icon": "cloud", "zh": "未知", "en": "Unknown"}

_CITY_FIELDS = ("city", "town", "village", "county", "suburb", "state_district", "state")


def configure(config: Mapping[str, Any] | None) -> None:
    global _CACHE_TTL
    mapping = dict(config or {})
    _CACHE_TTL = _clamp_int(
        mapping.get("cache_ttl"),
        minimum=60,
        maximum=3600,
        default=_DEFAULT_CACHE_TTL,
    )


def _clamp_int(
    value: Any,
    *,
    minimum: int,
    maximum: int,
    default: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


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
        sorted_keys = sorted(_cache, key=lambda item: _cache[item][0])
        for cache_key in sorted_keys[:100]:
            _cache.pop(cache_key, None)


def _remaining_timeout(deadline: float | None, *, minimum: float = 0.5) -> float | None:
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= minimum:
        return None
    return remaining


def _bounded_timeout(
    default_timeout: float,
    deadline: float | None,
    *,
    minimum: float = 0.5,
) -> float | None:
    remaining = _remaining_timeout(deadline, minimum=minimum)
    if remaining is None:
        return None
    return max(minimum, min(default_timeout, remaining))


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
    if has_cjk:
        trimmed = _trim_city_label_suffix(query)
        if trimmed and trimmed != query and trimmed not in expanded:
            expanded.append(trimmed)
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
    return _trim_city_label_suffix(text)


def _trim_city_label_suffix(value: str) -> str:
    text = str(value or "").strip()
    for suffix in _CITY_LABEL_TRIM_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)].strip()
    return text


def _sort_city_results(
    *,
    original_query: str,
    expanded_queries: list[str],
    results: list[dict[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda item: _rank_city_candidate(
            original_query=original_query,
            expanded_queries=expanded_queries,
            candidate=item,
        ),
        reverse=True,
    )[:count]


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


def get_wmo_info(code: int) -> dict[str, str]:
    return WMO_CODES.get(code, _DEFAULT_WMO)


def _make_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, headers=_REQUEST_HEADERS)


def _guess_query_language(value: str) -> str:
    if any("\u4e00" <= ch <= "\u9fff" for ch in str(value or "")):
        return "zh-CN"
    return "en"


def _coerce_number(value: Any) -> int | float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _coerce_float(value: Any) -> float | None:
    number = _coerce_number(value)
    if number is None:
        return None
    return float(number)


async def _nominatim_throttle() -> None:
    global _nominatim_last_ts
    async with _nominatim_lock:
        now = time.monotonic()
        gap = 1.0 - (now - _nominatim_last_ts)
        if gap > 0:
            await asyncio.sleep(gap)
        _nominatim_last_ts = time.monotonic()


def _approx_timezone(longitude: float) -> timezone:
    offset = round(longitude / 15.0)
    offset = max(-12, min(14, offset))
    return timezone(timedelta(hours=offset))


def _parse_iso_datetime(value: str, *, target_tz: timezone | None = None) -> datetime:
    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(target_tz or UTC)


def _symbol_base(symbol_code: str | None) -> str:
    symbol = str(symbol_code or "").strip().lower()
    for suffix in ("_day", "_night", "_polartwilight"):
        if symbol.endswith(suffix):
            return symbol[: -len(suffix)]
    return symbol


def _symbol_period(symbol_code: str | None) -> str | None:
    symbol = str(symbol_code or "").strip().lower()
    for suffix in ("day", "night", "polartwilight"):
        token = f"_{suffix}"
        if symbol.endswith(token):
            return suffix
    return None


def _symbol_to_weather(symbol_code: str | None) -> dict[str, Any]:
    base = _symbol_base(symbol_code)
    zh, en = _SYMBOL_TRANSLATIONS.get(base, ("未知", "Unknown"))

    if "thunder" in base:
        wmo = 95
    elif "snowshowers" in base:
        wmo = 85
    elif "snow" in base:
        wmo = 73 if "light" not in base else 71
        if "heavy" in base:
            wmo = 75
    elif "sleetshowers" in base:
        wmo = 85
    elif "sleet" in base:
        wmo = 77
    elif "rainshowers" in base:
        if "light" in base:
            wmo = 80
        elif "heavy" in base:
            wmo = 82
        else:
            wmo = 81
    elif "rain" in base:
        if "light" in base:
            wmo = 61
        elif "heavy" in base:
            wmo = 65
        else:
            wmo = 63
    elif "drizzle" in base:
        wmo = 51
    elif "fog" in base:
        wmo = 45
    elif base == "partlycloudy":
        wmo = 2
    elif base == "fair":
        wmo = 1
    elif base == "clearsky":
        wmo = 0
    elif base == "cloudy":
        wmo = 3
    else:
        wmo = 3

    return {"wmo": wmo, "zh": zh, "en": en}


def _symbol_is_day(symbol_code: str | None, *, local_dt: datetime | None = None) -> bool:
    period = _symbol_period(symbol_code)
    if period == "night":
        return False
    if period in {"day", "polartwilight"}:
        return True
    if local_dt is not None:
        return 6 <= local_dt.hour < 18
    return True


def _extract_symbol(entry: dict[str, Any]) -> str | None:
    data = entry.get("data", {}) or {}
    for key in ("next_1_hours", "next_6_hours", "next_12_hours"):
        summary = (data.get(key) or {}).get("summary") or {}
        symbol = summary.get("symbol_code")
        if symbol:
            return str(symbol)
    return None


def _to_local_entry(entry: dict[str, Any], *, tz: timezone) -> tuple[datetime, dict[str, Any]]:
    local_dt = _parse_iso_datetime(str(entry.get("time") or ""), target_tz=tz)
    return local_dt, entry


async def _fetch_met_timeseries(latitude: float, longitude: float) -> list[dict[str, Any]]:
    cache_key = f"met:{latitude:.2f}:{longitude:.2f}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    async with _make_client(_WEATHER_TIMEOUT) as client:
        resp = await client.get(
            _MET_FORECAST_URL,
            params={"lat": latitude, "lon": longitude},
        )
        resp.raise_for_status()
        payload = resp.json()

    timeseries = ((payload.get("properties") or {}).get("timeseries") or [])
    if not isinstance(timeseries, list) or not timeseries:
        raise RuntimeError("MET Norway weather payload is empty")

    _cache_set(cache_key, timeseries)
    return timeseries


async def get_weather_all(
    latitude: float,
    longitude: float,
    days: int = 3,
) -> dict[str, Any]:
    days = max(1, min(days, 7))
    cache_key = f"all:{latitude:.2f}:{longitude:.2f}:{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    timeseries = await _fetch_met_timeseries(latitude, longitude)
    tz = _approx_timezone(longitude)

    current_entry = timeseries[0]
    current_local_dt = _parse_iso_datetime(str(current_entry.get("time") or ""), target_tz=tz)
    current_details = (((current_entry.get("data") or {}).get("instant") or {}).get("details") or {})
    current_symbol = _extract_symbol(current_entry)
    current_condition = _symbol_to_weather(current_symbol)
    current_wmo = get_wmo_info(int(current_condition["wmo"]))

    current_out = {
        "temperature": _coerce_float(current_details.get("air_temperature")),
        "apparent_temperature": _coerce_float(current_details.get("air_temperature")),
        "weather_code": int(current_condition["wmo"]),
        "weather_icon": current_wmo["icon"],
        "weather_text_zh": str(current_condition["zh"]),
        "weather_text_en": str(current_condition["en"]),
        "humidity": _coerce_number(current_details.get("relative_humidity")),
        "wind_speed": (
            round(float(current_details["wind_speed"]) * 3.6, 1)
            if _coerce_float(current_details.get("wind_speed")) is not None
            else None
        ),
        "uv_index": None,
        "is_day": _symbol_is_day(current_symbol, local_dt=current_local_dt),
    }

    hourly_out: list[dict[str, Any]] = []
    for index, entry in enumerate(timeseries[:24]):
        local_dt = _parse_iso_datetime(str(entry.get("time") or ""), target_tz=tz)
        details = (((entry.get("data") or {}).get("instant") or {}).get("details") or {})
        symbol = _extract_symbol(entry)
        condition = _symbol_to_weather(symbol)
        wmo_info = get_wmo_info(int(condition["wmo"]))
        hourly_out.append(
            {
                "time": local_dt.strftime("%H:%M"),
                "temperature": _coerce_float(details.get("air_temperature")),
                "weather_code": int(condition["wmo"]),
                "weather_icon": wmo_info["icon"],
                "weather_text_zh": str(condition["zh"]),
                "weather_text_en": str(condition["en"]),
                "is_current": index == 0,
            }
        )

    grouped: dict[str, dict[str, Any]] = {}
    for entry in timeseries[:24 * 8]:
        local_dt = _parse_iso_datetime(str(entry.get("time") or ""), target_tz=tz)
        local_date = local_dt.date().isoformat()
        bucket = grouped.setdefault(
            local_date,
            {
                "date": local_date,
                "temp_max": None,
                "temp_min": None,
                "best_symbol": None,
                "best_distance": 999,
            },
        )
        details = (((entry.get("data") or {}).get("instant") or {}).get("details") or {})
        temp = _coerce_float(details.get("air_temperature"))
        if temp is not None:
            bucket["temp_max"] = temp if bucket["temp_max"] is None else max(bucket["temp_max"], temp)
            bucket["temp_min"] = temp if bucket["temp_min"] is None else min(bucket["temp_min"], temp)

        symbol = _extract_symbol(entry)
        if symbol:
            distance = abs(local_dt.hour - 12)
            if distance < bucket["best_distance"]:
                bucket["best_distance"] = distance
                bucket["best_symbol"] = symbol

    daily_out: list[dict[str, Any]] = []
    for date_key in sorted(grouped.keys())[:days]:
        bucket = grouped[date_key]
        condition = _symbol_to_weather(bucket.get("best_symbol"))
        wmo_info = get_wmo_info(int(condition["wmo"]))
        daily_out.append(
            {
                "date": bucket["date"],
                "temp_max": bucket["temp_max"],
                "temp_min": bucket["temp_min"],
                "weather_code": int(condition["wmo"]),
                "weather_icon": wmo_info["icon"],
                "weather_text_zh": str(condition["zh"]),
                "weather_text_en": str(condition["en"]),
                "sunrise": None,
                "sunset": None,
            }
        )

    result = {
        "current": current_out,
        "daily": daily_out,
        "hourly": hourly_out,
    }
    _cache_set(cache_key, result)
    return result


async def get_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
    all_data = await get_weather_all(latitude, longitude)
    return all_data["current"]


async def get_forecast(latitude: float, longitude: float, days: int = 3) -> list[dict[str, Any]]:
    all_data = await get_weather_all(latitude, longitude, days)
    return all_data["daily"]


async def get_air_quality(latitude: float, longitude: float) -> dict[str, Any]:
    _latitude = latitude
    _longitude = longitude
    return {"aqi": None, "pm2_5": None, "pm10": None, "european_aqi": None}


async def _search_city_nominatim(
    name: str,
    count: int,
    *,
    timeout: float = _NOMINATIM_TIMEOUT,
) -> list[dict[str, Any]]:
    try:
        await _nominatim_throttle()
        async with _make_client(timeout) as client:
            resp = await client.get(
                _NOMINATIM_SEARCH_URL,
                params={
                    "q": name,
                    "format": "jsonv2",
                    "limit": count,
                    "accept-language": _guess_query_language(name),
                    "addressdetails": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("Nominatim search timeout for query='{}' timeout={}s", name, timeout)
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


async def _search_city_open_meteo(
    name: str,
    count: int,
    *,
    timeout: float = _NOMINATIM_TIMEOUT,
) -> list[dict[str, Any]]:
    """Compatibility alias retained for the executor fallback path."""
    return await _search_city_nominatim(name, count, timeout=timeout)


async def search_city(name: str, count: int = 5) -> list[dict[str, Any]]:
    if not name or not name.strip():
        return []

    query = name.strip()
    cache_key = f"geo:{query}:{count}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    queries = _expand_city_queries(query)
    merged_results: list[dict[str, Any]] = []
    deadline = time.monotonic() + _CITY_LOOKUP_TOTAL_TIMEOUT

    for candidate in queries[:3]:
        timeout = _bounded_timeout(_GEOCODING_TIMEOUT, deadline)
        if timeout is None:
            break
        results = await _search_city_nominatim(candidate, count, timeout=timeout)
        merged_results = _merge_city_results(
            merged_results,
            results,
            limit=max(count * 4, count),
        )
        if count == 1 and merged_results:
            break

    merged_results = _sort_city_results(
        original_query=query,
        expanded_queries=queries,
        results=merged_results,
        count=count,
    )
    _cache_set(cache_key, merged_results)
    return merged_results


async def _reverse_nominatim(latitude: float, longitude: float) -> dict[str, Any] | None:
    try:
        await _nominatim_throttle()
        async with _make_client(_NOMINATIM_TIMEOUT) as client:
            resp = await client.get(
                _NOMINATIM_REVERSE_URL,
                params={
                    "lat": latitude,
                    "lon": longitude,
                    "format": "jsonv2",
                    "zoom": 14,
                    "accept-language": "zh-CN",
                    "addressdetails": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(
            "Nominatim reverse error for lat={} lon={}: {}",
            latitude,
            longitude,
            _describe_exception(exc),
        )
        return None

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

    if not city_name:
        return None

    return {
        "name": city_name,
        "country": address.get("country", ""),
        "admin1": address.get("state", ""),
        "latitude": latitude,
        "longitude": longitude,
    }


async def reverse_geocode(latitude: float, longitude: float) -> dict[str, Any] | None:
    cache_key = f"rgeo:{latitude:.2f}:{longitude:.2f}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    result = await _reverse_nominatim(latitude, longitude)
    if result:
        _cache_set(cache_key, result)
    return result


configure({})
