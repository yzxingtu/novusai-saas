/**
 * 天气数据 Composable (v2)
 *
 * - 合并 current / forecast / hourly / aqi 数据获取
 * - AbortController 请求去重
 * - localStorage 缓存上次成功数据（弱网 fallback）
 * - 骨架屏 initialLoading 状态
 * - 修复 geolocate：先反向地理编码，重试 1 次，降级提示
 */

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { requestClient } from '@novus/plugin-shared';

// ── 类型 ──

export interface WeatherCurrent {
  temperature: number | null;
  apparent_temperature: number | null;
  weather_code: number;
  weather_icon: string;
  weather_text_zh: string;
  weather_text_en: string;
  humidity: number | null;
  wind_speed: number | null;
  uv_index: number | null;
  is_day: boolean;
}

export interface WeatherForecastDay {
  date: string;
  temp_max: number | null;
  temp_min: number | null;
  weather_code: number;
  weather_icon: string;
  weather_text_zh: string;
  weather_text_en: string;
  sunrise: string | null;
  sunset: string | null;
}

export interface WeatherHourly {
  time: string;
  temperature: number | null;
  weather_code: number;
  weather_icon: string;
  weather_text_zh: string;
  weather_text_en: string;
  is_current?: boolean;
}

export interface AirQuality {
  aqi: number | null;
  pm2_5: number | null;
  pm10: number | null;
  european_aqi: number | null;
}

export interface CityInfo {
  name: string;
  country?: string;
  admin1?: string;
  latitude: number;
  longitude: number;
}

interface PluginConfig {
  default_city?: string;
  temperature_unit?: string;
  forecast_days?: number;
  cache_ttl?: number;
  auto_refresh?: boolean;
}

interface WeatherLocalConfig {
  city: string;
  latitude: number;
  longitude: number;
  recentCities: CityInfo[];
}

interface CachedWeatherData {
  current: WeatherCurrent | null;
  forecast: WeatherForecastDay[];
  hourly: WeatherHourly[];
  airQuality: AirQuality | null;
  timestamp: number;
}

// ── 热门城市 ──

export const POPULAR_CITIES: CityInfo[] = [
  { name: '北京', latitude: 39.9042, longitude: 116.4074, country: 'China' },
  { name: '上海', latitude: 31.2304, longitude: 121.4737, country: 'China' },
  { name: '广州', latitude: 23.1291, longitude: 113.2644, country: 'China' },
  { name: '深圳', latitude: 22.5431, longitude: 114.0579, country: 'China' },
  { name: '杭州', latitude: 30.2741, longitude: 120.1551, country: 'China' },
  { name: '成都', latitude: 30.5728, longitude: 104.0668, country: 'China' },
  { name: '武汉', latitude: 30.5928, longitude: 114.3055, country: 'China' },
  { name: '南京', latitude: 32.0603, longitude: 118.7969, country: 'China' },
  { name: '重庆', latitude: 29.4316, longitude: 106.9123, country: 'China' },
  { name: '西安', latitude: 34.3416, longitude: 108.9398, country: 'China' },
  { name: '苏州', latitude: 31.2990, longitude: 120.5853, country: 'China' },
  { name: '天津', latitude: 39.3434, longitude: 117.3616, country: 'China' },
];

// ── 常量 ──

const STORAGE_KEY = 'novusai_weather_config';
const WEATHER_DATA_KEY = 'novusai_weather_data';
const MAX_RECENT_CITIES = 5;
const STALE_THRESHOLD = 30 * 60 * 1000; // 30 min

const DEFAULT_LOCAL: WeatherLocalConfig = {
  city: '上海',
  latitude: 31.2304,
  longitude: 121.4737,
  recentCities: [
    { name: '上海', latitude: 31.2304, longitude: 121.4737, country: 'China' },
  ],
};

function loadLocalConfig(): WeatherLocalConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<WeatherLocalConfig>;
      return {
        city: parsed.city || DEFAULT_LOCAL.city,
        latitude: parsed.latitude ?? DEFAULT_LOCAL.latitude,
        longitude: parsed.longitude ?? DEFAULT_LOCAL.longitude,
        recentCities:
          Array.isArray(parsed.recentCities) && parsed.recentCities.length > 0
            ? parsed.recentCities
            : DEFAULT_LOCAL.recentCities,
      };
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_LOCAL, recentCities: [...DEFAULT_LOCAL.recentCities] };
}

function saveLocalConfig(cfg: WeatherLocalConfig): void {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg)); } catch { /* ignore */ }
}

function loadCachedWeather(): CachedWeatherData | null {
  try {
    const raw = localStorage.getItem(WEATHER_DATA_KEY);
    if (raw) return JSON.parse(raw) as CachedWeatherData;
  } catch { /* ignore */ }
  return null;
}

function saveCachedWeather(data: CachedWeatherData): void {
  try { localStorage.setItem(WEATHER_DATA_KEY, JSON.stringify(data)); } catch { /* ignore */ }
}

// ── Composable ──

export function useWeather() {
  const router = useRouter();
  const localConfig = ref<WeatherLocalConfig>(loadLocalConfig());
  const pluginConfig = ref<PluginConfig>({});

  const current = ref<WeatherCurrent | null>(null);
  const forecast = ref<WeatherForecastDay[]>([]);
  const hourly = ref<WeatherHourly[]>([]);
  const airQuality = ref<AirQuality | null>(null);

  const loading = ref(false);
  const initialLoading = ref(true);
  const error = ref<string | null>(null);
  const locating = ref(false);
  const locateError = ref<string | null>(null);
  const showCitySelector = ref(false);
  const isStale = ref(false);

  let refreshTimer: ReturnType<typeof setInterval> | null = null;
  let abortController: AbortController | null = null;

  const cityName = computed(() => localConfig.value.city);
  const recentCities = computed(() => localConfig.value.recentCities);

  const apiBase = computed(() => {
    const path = router.currentRoute.value.path;
    const prefix = path.startsWith('/admin') ? '/admin' : '/tenant';
    return `${prefix}/plugins/weather-widget/api`;
  });

  // ── 插件配置 ──

  async function fetchPluginConfig(): Promise<void> {
    try {
      const resp = await requestClient.get<{ config: PluginConfig }>(
        `${apiBase.value}/config`,
      );
      if (resp?.config) pluginConfig.value = resp.config;
    } catch { /* use defaults */ }
  }

  // ── 数据获取 ──

  async function fetchAll(): Promise<void> {
    if (abortController) abortController.abort();
    abortController = new AbortController();

    loading.value = true;
    error.value = null;
    isStale.value = false;

    const { latitude, longitude } = localConfig.value;

    try {
      const [weatherResp, aqiResp] = await Promise.all([
        requestClient.get<{
          weather: WeatherCurrent;
          forecast?: WeatherForecastDay[];
          hourly?: WeatherHourly[];
        }>(`${apiBase.value}/current`, {
          params: { lat: latitude, lon: longitude },
        }),
        requestClient.get<{ air_quality: AirQuality }>(
          `${apiBase.value}/air-quality`,
          { params: { lat: latitude, lon: longitude } },
        ).catch(() => null),
      ]);

      if (weatherResp?.weather) {
        current.value = weatherResp.weather;
        error.value = null;
      }

      // Fetch forecast + hourly in parallel
      const [forecastResp, hourlyResp] = await Promise.all([
        requestClient.get<{ forecast: WeatherForecastDay[] }>(
          `${apiBase.value}/forecast`,
          { params: { lat: latitude, lon: longitude } },
        ).catch(() => null),
        requestClient.get<{ hourly: WeatherHourly[] }>(
          `${apiBase.value}/hourly`,
          { params: { lat: latitude, lon: longitude } },
        ).catch(() => null),
      ]);

      if (forecastResp?.forecast) forecast.value = forecastResp.forecast;
      if (hourlyResp?.hourly) hourly.value = hourlyResp.hourly;
      if (aqiResp?.air_quality) airQuality.value = aqiResp.air_quality;

      saveCachedWeather({
        current: current.value,
        forecast: forecast.value,
        hourly: hourly.value,
        airQuality: airQuality.value,
        timestamp: Date.now(),
      });
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : String(err);

      const cached = loadCachedWeather();
      if (cached && cached.current) {
        current.value = cached.current;
        forecast.value = cached.forecast;
        hourly.value = cached.hourly;
        airQuality.value = cached.airQuality;
        isStale.value = Date.now() - cached.timestamp > STALE_THRESHOLD;
      }
    } finally {
      loading.value = false;
      initialLoading.value = false;
    }
  }

  async function searchCity(name: string): Promise<CityInfo[]> {
    try {
      const resp = await requestClient.get<{ cities: CityInfo[] }>(
        `${apiBase.value}/geocoding`, { params: { name, count: 8 } },
      );
      return resp?.cities ?? [];
    } catch { return []; }
  }

  // ── 定位 ──

  async function geolocate(): Promise<void> {
    if (!navigator.geolocation) return;
    locating.value = true;
    locateError.value = null;

    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 300000,
        });
      });

      const { latitude, longitude } = pos.coords;
      let resolvedCity: CityInfo | null = null;

      // Attempt reverse geocode with 1 retry
      for (let attempt = 0; attempt < 2; attempt++) {
        try {
          const resp = await requestClient.get<{ cities: CityInfo[] }>(
            `${apiBase.value}/geocoding`,
            { params: { lat: latitude, lon: longitude } },
          );
          if (resp?.cities?.length && resp.cities[0]!.name) {
            resolvedCity = resp.cities[0]!;
            break;
          }
        } catch { /* retry */ }
        if (attempt === 0) await new Promise(r => setTimeout(r, 1000));
      }

      if (resolvedCity) {
        selectCity(resolvedCity);
      } else {
        selectCity({ name: `${latitude.toFixed(2)}, ${longitude.toFixed(2)}`, latitude, longitude });
        locateError.value = 'locate_fallback';
      }
    } catch {
      locateError.value = 'locate_failed';
    } finally {
      locating.value = false;
    }
  }

  // ── 城市切换 ──

  function selectCity(city: CityInfo): void {
    localConfig.value.city = city.name;
    localConfig.value.latitude = city.latitude;
    localConfig.value.longitude = city.longitude;
    const recent = localConfig.value.recentCities.filter(
      (c: CityInfo) => !(Math.abs(c.latitude - city.latitude) < 0.01 && Math.abs(c.longitude - city.longitude) < 0.01),
    );
    recent.unshift(city);
    localConfig.value.recentCities = recent.slice(0, MAX_RECENT_CITIES);
    saveLocalConfig(localConfig.value);
    showCitySelector.value = false;
    fetchAll();
  }

  // ── 生命周期 ──

  onMounted(async () => {
    // Show cached data immediately while loading fresh data
    const cached = loadCachedWeather();
    if (cached?.current) {
      current.value = cached.current;
      forecast.value = cached.forecast;
      hourly.value = cached.hourly;
      airQuality.value = cached.airQuality;
      isStale.value = Date.now() - cached.timestamp > STALE_THRESHOLD;
      initialLoading.value = false;
    }

    await fetchPluginConfig();
    const refreshInterval = (pluginConfig.value.cache_ttl ?? 600) * 1000;
    const autoRefresh = pluginConfig.value.auto_refresh ?? true;

    await fetchAll();

    if (autoRefresh) {
      refreshTimer = setInterval(fetchAll, refreshInterval);
    }
  });

  onBeforeUnmount(() => {
    if (refreshTimer) clearInterval(refreshTimer);
    if (abortController) abortController.abort();
  });

  watch(() => localConfig.value.city, () => saveLocalConfig(localConfig.value));

  return {
    cityName, recentCities, current, forecast, hourly, airQuality,
    loading, initialLoading, error, locating, locateError,
    showCitySelector, isStale, pluginConfig,
    fetchAll, searchCity, selectCity, geolocate,
  };
}
